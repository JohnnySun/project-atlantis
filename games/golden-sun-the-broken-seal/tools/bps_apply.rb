#!/usr/bin/env ruby
# Minimal BPS1 patch applicator with all three CRC32 integrity checks.

require "zlib"

abort "usage: bps_apply.rb SOURCE PATCH OUTPUT" unless ARGV.length == 3
source_path, patch_path, output_path = ARGV
source = File.binread(source_path)
patch = File.binread(patch_path)
abort "not a BPS1 patch" unless patch.start_with?("BPS1")
abort "truncated BPS patch" if patch.bytesize < 16

cursor = 4
read_number = lambda do
  value = 0
  shift = 1
  loop do
    abort "truncated BPS patch" if cursor >= patch.bytesize
    byte = patch.getbyte(cursor)
    cursor += 1
    value += (byte & 0x7f) * shift
    break if (byte & 0x80) != 0
    shift <<= 7
    value += shift
  end
  value
end

read_signed = lambda do
  value = read_number.call
  magnitude = value >> 1
  (value & 1) == 1 ? -magnitude : magnitude
end

source_size = read_number.call
target_size = read_number.call
metadata_size = read_number.call
abort "source size mismatch" unless source.bytesize == source_size
abort "truncated BPS metadata" if cursor + metadata_size > patch.bytesize - 12
cursor += metadata_size

target = +""
target.force_encoding(Encoding::BINARY)
source_relative = 0
target_relative = 0

while target.bytesize < target_size
  abort "truncated BPS actions" if cursor >= patch.bytesize - 12
  action = read_number.call
  length = (action >> 2) + 1

  case action & 3
  when 0 # SourceRead
    offset = target.bytesize
    bytes = source.byteslice(offset, length)
    abort "SourceRead outside source" unless bytes&.bytesize == length
    target << bytes
  when 1 # TargetRead
    abort "TargetRead outside patch" if cursor + length > patch.bytesize - 12
    target << patch.byteslice(cursor, length)
    cursor += length
  when 2 # SourceCopy
    source_relative += read_signed.call
    bytes = source.byteslice(source_relative, length)
    abort "SourceCopy outside source" unless bytes&.bytesize == length
    target << bytes
    source_relative += length
  when 3 # TargetCopy (bytewise to permit overlapping copies)
    target_relative += read_signed.call
    length.times do
      abort "TargetCopy outside produced target" unless target_relative.between?(0, target.bytesize - 1)
      target << target.getbyte(target_relative)
      target_relative += 1
    end
  end

  abort "target grew beyond declared size" if target.bytesize > target_size
end

abort "unexpected data before BPS checksums" unless cursor == patch.bytesize - 12
source_crc, target_crc, patch_crc = patch.byteslice(-12, 12).unpack("V3")
abort "source CRC32 mismatch" unless Zlib.crc32(source) == source_crc
abort "target CRC32 mismatch" unless Zlib.crc32(target) == target_crc
abort "patch CRC32 mismatch" unless Zlib.crc32(patch.byteslice(0, patch.bytesize - 4)) == patch_crc

File.binwrite(output_path, target)
puts "source CRC32: %08x" % source_crc
puts "target CRC32: %08x" % target_crc
puts "patch CRC32:  %08x" % patch_crc
puts "output bytes: #{target.bytesize}"
