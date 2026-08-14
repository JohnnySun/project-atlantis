#!/usr/bin/env ruby

require "optparse"

options = {}
OptionParser.new do |parser|
  parser.banner = <<~USAGE
    usage: extract-huffman-text-ids.rb --rom ROM --output FILE --count N \
      --huffman-pointer-table OFFSET --string-pointer-table OFFSET
  USAGE
  parser.on("--rom FILE") { |value| options[:rom] = value }
  parser.on("--output FILE") { |value| options[:output] = value }
  parser.on("--count N", Integer) { |value| options[:count] = value }
  parser.on("--huffman-pointer-table OFFSET") { |value| options[:huffman_pointer_table] = Integer(value) }
  parser.on("--string-pointer-table OFFSET") { |value| options[:string_pointer_table] = Integer(value) }
end.parse!

required = %i[rom output count huffman_pointer_table string_pointer_table]
abort "missing required options" unless required.all? { |key| options.key?(key) }

rom = File.binread(options[:rom])

def u16(data, offset)
  bytes = data.byteslice(offset, 2)
  abort "16-bit read outside ROM at 0x%x" % offset unless bytes&.bytesize == 2
  bytes.unpack1("v")
end

def u32(data, offset)
  bytes = data.byteslice(offset, 4)
  abort "32-bit read outside ROM at 0x%x" % offset unless bytes&.bytesize == 4
  bytes.unpack1("V")
end

def rom_offset(pointer, size)
  abort "not a GBA ROM pointer: 0x%08x" % pointer unless (pointer & 0xff00_0000) == 0x0800_0000
  offset = pointer & 0x00ff_ffff
  abort "ROM pointer outside file: 0x%08x" % pointer unless offset < size
  offset
end

class BitReader
  def initialize(data, byte_offset)
    @data = data
    @byte_offset = byte_offset
    @bits = 0
    @available = 0
  end

  def next_bit
    if @available.zero?
      abort "bit reader outside ROM" if @byte_offset >= @data.bytesize
      @bits = @data.getbyte(@byte_offset)
      @byte_offset += 1
      @available = 8
    end
    bit = @bits & 1
    @bits >>= 1
    @available -= 1
    bit
  end
end

def subtree_leaf_count(reader)
  leaves = 0
  level = 0
  while level >= 0
    if reader.next_bit == 1
      leaves += 1
      level -= 1
    else
      level += 1
    end
  end
  leaves
end

def leaf_value(data, tree_offset, leaf_id)
  packed_offset = leaf_id + (leaf_id >> 1)
  pointer = tree_offset - packed_offset
  byte0 = data.getbyte(pointer - 1)
  byte1 = data.getbyte(pointer - 2)
  abort "invalid Huffman leaf" unless byte0 && byte1
  if leaf_id.odd?
    ((byte0 & 0x0f) << 8) | byte1
  else
    (byte0 << 4) | (byte1 >> 4)
  end
end

def decompress_character(data, reader, previous, pointer_table)
  pointer_pair = pointer_table + (previous >> 8) * 8
  tree_data = rom_offset(u32(data, pointer_pair), data.bytesize)
  tree_offsets = rom_offset(u32(data, pointer_pair + 4), data.bytesize)
  relative = u16(data, tree_offsets + (previous & 0xff) * 2)
  abort "missing Huffman context for 0x%03x" % previous if relative == 0x8000

  tree_offset = tree_data + relative
  tree_reader = BitReader.new(data, tree_offset)
  leaf_id = 0
  while tree_reader.next_bit.zero?
    leaf_id += subtree_leaf_count(tree_reader) if reader.next_bit == 1
  end
  leaf_value(data, tree_offset, leaf_id)
end

strings = []
string_id = 0
group = 0
while string_id < options[:count]
  pair_offset = options[:string_pointer_table] + group * 8
  data_offset = rom_offset(u32(rom, pair_offset), rom.bytesize)
  lengths_offset = rom_offset(u32(rom, pair_offset + 4), rom.bytesize)
  length_cursor = lengths_offset

  [256, options[:count] - string_id].min.times do
    reader = BitReader.new(rom, data_offset)
    previous = 0
    values = []
    loop do
      value = decompress_character(rom, reader, previous, options[:huffman_pointer_table])
      break if value.zero?
      values << value
      previous = value
      abort "string #{string_id} exceeds safety limit" if values.length > 4096
    end
    strings << values

    compressed_length = 0
    loop do
      length_part = rom.getbyte(length_cursor)
      abort "missing compressed length for string #{string_id}" unless length_part
      length_cursor += 1
      compressed_length += length_part
      break unless length_part == 0xff
    end
    data_offset += compressed_length
    string_id += 1
  end
  group += 1
end

File.open(options[:output], "w") do |file|
  file.puts "id\tlength\tcode_units"
  strings.each_with_index do |values, id|
    units = values.map { |value| "%04x" % value }.join(" ")
    file.puts [id, values.length, units].join("\t")
  end
end

warn "extracted #{strings.length} strings to #{options[:output]}"
