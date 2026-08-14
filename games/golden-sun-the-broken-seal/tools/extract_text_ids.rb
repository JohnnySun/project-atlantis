#!/usr/bin/env ruby
# Extract Golden Sun string streams as numeric glyph/control IDs.
# Supports the Japanese Huffman layout and the 2024 Chinese direct-pointer layout.

require "optparse"

options = { count: 11_115 }
OptionParser.new do |parser|
  parser.banner = "usage: extract_text_ids.rb --mode MODE --rom ROM --output FILE"
  parser.on("--mode MODE", %w[jp-huffman cn-direct]) { |value| options[:mode] = value }
  parser.on("--rom FILE") { |value| options[:rom] = value }
  parser.on("--output FILE") { |value| options[:output] = value }
  parser.on("--count N", Integer) { |value| options[:count] = value }
end.parse!

abort "--mode, --rom and --output are required" unless options.values_at(:mode, :rom, :output).all?
rom = File.binread(options[:rom])

def u16(data, offset)
  data.byteslice(offset, 2).unpack1("v")
end

def u32(data, offset)
  data.byteslice(offset, 4).unpack1("V")
end

def rom_offset(pointer, size)
  offset = pointer & 0x00ff_ffff
  abort "ROM pointer outside file: 0x%08x" % pointer unless offset < size
  offset
end

class BitReader
  attr_reader :byte_offset

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
  offset = leaf_id + (leaf_id >> 1)
  pointer = tree_offset - offset
  byte0 = data.getbyte(pointer - 1)
  byte1 = data.getbyte(pointer - 2)
  abort "invalid Huffman leaf" unless byte0 && byte1
  if (leaf_id & 1) == 1
    ((byte0 & 0x0f) << 8) | byte1
  else
    (byte0 << 4) | (byte1 >> 4)
  end
end

def decompress_character(data, string_reader, previous, huffman_pointer_table)
  group = previous >> 8
  index = previous & 0xff
  pointer_pair = huffman_pointer_table + group * 8
  tree_data = rom_offset(u32(data, pointer_pair), data.bytesize)
  tree_offsets = rom_offset(u32(data, pointer_pair + 4), data.bytesize)
  relative = u16(data, tree_offsets + index * 2)
  abort "missing Huffman context for 0x%02x" % previous if relative == 0x8000
  tree_offset = tree_data + relative
  tree_reader = BitReader.new(data, tree_offset)
  leaf_id = 0
  while tree_reader.next_bit.zero?
    leaf_id += subtree_leaf_count(tree_reader) if string_reader.next_bit == 1
  end
  leaf_value(data, tree_offset, leaf_id)
end

strings = []

case options[:mode]
when "jp-huffman"
  # Japanese AGSJ01 literals, recovered from the original decompressor.
  huffman_pointer_table = 0x03bb68
  string_pointer_table = 0x06c040
  string_id = 0
  group = 0
  while string_id < options[:count]
    data_offset = rom_offset(u32(rom, string_pointer_table + group * 8), rom.bytesize)
    lengths_offset = rom_offset(u32(rom, string_pointer_table + group * 8 + 4), rom.bytesize)

    256.times do |within_group|
      break if string_id >= options[:count]
      reader = BitReader.new(rom, data_offset)
      previous = 0
      values = []
      loop do
        value = decompress_character(rom, reader, previous, huffman_pointer_table)
        break if value.zero?
        values << value
        previous = value
      end
      strings << values

      length = rom.getbyte(lengths_offset + within_group)
      abort "missing length for string #{string_id}" unless length
      while length == 0xff
        data_offset += length
        within_group += 1
        length = rom.getbyte(lengths_offset + within_group)
      end
      data_offset += length
      string_id += 1
    end
    group += 1
  end
when "cn-direct"
  pointer_table = 0x800000
  options[:count].times do |string_id|
    offset = rom_offset(u32(rom, pointer_table + string_id * 4), rom.bytesize)
    values = []
    loop do
      first_byte = rom.getbyte(offset)
      abort "Chinese string #{string_id} points outside ROM" unless first_byte
      offset += 1
      break if first_byte.zero?
      # The replacement engine retains single-byte control codes below 0x20,
      # while printable glyph IDs are stored as little-endian 16-bit values.
      if first_byte < 0x20
        value = first_byte
      else
        second_byte = rom.getbyte(offset)
        abort "truncated glyph in Chinese string #{string_id}" unless second_byte
        offset += 1
        value = first_byte | (second_byte << 8)
      end
      values << value
      abort "unterminated Chinese string #{string_id}" if values.length > 4096
    end
    strings << values
  end
end

File.open(options[:output], "wb") do |file|
  file.puts "id\tlength\tcode_units"
  strings.each_with_index do |values, id|
    file.puts [id, values.length, values.map { |value| "%04x" % value }.join(" ")].join("\t")
  end
end

warn "extracted #{strings.length} strings to #{options[:output]}"
