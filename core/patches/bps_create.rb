#!/usr/bin/env ruby

require "zlib"

abort "usage: bps_create.rb SOURCE TARGET OUTPUT.bps" unless ARGV.length == 3
source_path, target_path, output_path = ARGV
source = File.binread(source_path)
target = File.binread(target_path)

def encode_number(number)
  abort "cannot encode a negative BPS number" if number.negative?
  output = +""
  output.force_encoding(Encoding::BINARY)
  loop do
    byte = number & 0x7f
    number >>= 7
    if number.zero?
      output << (byte | 0x80)
      break
    end
    output << byte
    number -= 1
  end
  output
end

patch = +"BPS1"
patch.force_encoding(Encoding::BINARY)
patch << encode_number(source.bytesize)
patch << encode_number(target.bytesize)
patch << encode_number(0)

cursor = 0
while cursor < target.bytesize
  source_read = cursor < source.bytesize && source.getbyte(cursor) == target.getbyte(cursor)
  start = cursor
  cursor += 1
  while cursor < target.bytesize
    equal = cursor < source.bytesize && source.getbyte(cursor) == target.getbyte(cursor)
    break if equal != source_read
    cursor += 1
  end
  length = cursor - start
  action_type = source_read ? 0 : 1
  patch << encode_number(((length - 1) << 2) | action_type)
  patch << target.byteslice(start, length) unless source_read
end

source_crc = Zlib.crc32(source)
target_crc = Zlib.crc32(target)
patch << [source_crc, target_crc].pack("V2")
patch_crc = Zlib.crc32(patch)
patch << [patch_crc].pack("V")
File.binwrite(output_path, patch)

puts "source CRC32: %08x" % source_crc
puts "target CRC32: %08x" % target_crc
puts "patch CRC32:  %08x" % patch_crc
puts "patch bytes:  #{patch.bytesize}"
