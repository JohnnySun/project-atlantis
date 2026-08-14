#!/usr/bin/env ruby

require "optparse"

options = {
  single_font: 0x05a8cc,
  extended_font: 0x05bf8c,
  scale: 4,
  columns: 12
}

OptionParser.new do |parser|
  parser.banner = "usage: render-original-glyphs.rb --rom ROM --output FILE.ppm ID..."
  parser.on("--rom FILE") { |value| options[:rom] = value }
  parser.on("--output FILE") { |value| options[:output] = value }
  parser.on("--single-font OFFSET") { |value| options[:single_font] = Integer(value) }
  parser.on("--extended-font OFFSET") { |value| options[:extended_font] = Integer(value) }
  parser.on("--scale N", Integer) { |value| options[:scale] = value }
  parser.on("--columns N", Integer) { |value| options[:columns] = value }
end.parse!

abort "missing --rom, --output, or glyph IDs" unless options[:rom] && options[:output] && !ARGV.empty?
abort "scale and columns must be positive" unless options[:scale].positive? && options[:columns].positive?

rom = File.binread(options[:rom])
glyph_ids = ARGV.map { |value| Integer(value, 16) & 0x3fff }
glyph_width = 16
glyph_height = 12
cell_width = glyph_width * options[:scale]
cell_height = glyph_height * options[:scale]
columns = [options[:columns], glyph_ids.length].min
rows = (glyph_ids.length.to_f / columns).ceil
width = columns * cell_width
height = rows * cell_height
pixels = Array.new(width * height * 3, 255)

glyph_ids.each_with_index do |glyph_id, index|
  if glyph_id <= 0xff
    abort "single-byte glyph below 0x20: 0x%04x" % glyph_id if glyph_id < 0x20
    offset = options[:single_font] + (glyph_id - 0x20) * 26
    words = rom.byteslice(offset, 26)&.unpack("v13")
    abort "glyph 0x%04x outside ROM" % glyph_id unless words
    actual_width, *row_words = words
    abort "invalid width #{actual_width} for glyph 0x%04x" % glyph_id unless (1..16).cover?(actual_width)
  else
    offset = options[:extended_font] + (glyph_id - 0x100) * 24
    row_words = rom.byteslice(offset, 24)&.unpack("v12")
    abort "glyph 0x%04x outside ROM" % glyph_id unless row_words
    actual_width = 10
  end

  origin_x = (index % columns) * cell_width
  origin_y = (index / columns) * cell_height
  row_words.each_with_index do |word, y|
    actual_width.times do |x|
      next if (word & (1 << (15 - x))).zero?
      options[:scale].times do |dy|
        options[:scale].times do |dx|
          pixel_x = origin_x + x * options[:scale] + dx
          pixel_y = origin_y + y * options[:scale] + dy
          position = (pixel_y * width + pixel_x) * 3
          pixels[position, 3] = [0, 0, 0]
        end
      end
    end
  end
end

File.open(options[:output], "wb") do |file|
  file.write("P6\n#{width} #{height}\n255\n")
  file.write(pixels.pack("C*"))
end

warn "rendered #{glyph_ids.length} glyphs to #{options[:output]}"
