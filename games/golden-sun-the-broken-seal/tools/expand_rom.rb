#!/usr/bin/env ruby
# The commercial AGSJ01 ROM is 8 MiB with only ~43 KiB of blank tail space --
# not enough room for translated text, an expanded Huffman table and new
# glyph rasters. Pad the ROM with zero bytes up to a larger power-of-two-ish
# size so a later build step has a blank region to insert data into.
#
# This mirrors the precedent already documented in
# research/audit-20260814.md: the 2024 public-beta CN patch grew this same
# ROM from 8,388,608 to 11,594,160 bytes and is confirmed to boot in mGBA.
# The GBA address space maps 0x08000000-0x09FFFFFF (32 MiB) for ROM
# regardless of the original cartridge's physical size, so a larger file is
# valid as long as nothing reads past what we explicitly populate.

require "optparse"

options = {}
OptionParser.new do |parser|
  parser.banner = "usage: expand_rom.rb --rom ROM --size BYTES --output ROM"
  parser.on("--rom FILE") { |value| options[:rom] = value }
  parser.on("--size N", Integer) { |value| options[:size] = value }
  parser.on("--output FILE") { |value| options[:output] = value }
end.parse!

required = %i[rom size output]
abort "missing required options" unless required.all? { |key| options[key] }

rom = File.binread(options[:rom])
abort "target size #{options[:size]} is not larger than source size #{rom.bytesize}" unless options[:size] > rom.bytesize

padded = rom + ("\0" * (options[:size] - rom.bytesize))
File.binwrite(options[:output], padded)

warn "expanded #{options[:rom]} (#{rom.bytesize} bytes) to #{options[:output]} (#{padded.bytesize} bytes)"
warn "blank insertable region: 0x%06x..0x%06x (%d bytes)" % [rom.bytesize, padded.bytesize - 1, padded.bytesize - rom.bytesize]
