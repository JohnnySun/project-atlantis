#!/usr/bin/env ruby

require "fileutils"
require "optparse"

options = {
  single_font: 0x05a8cc,
  extended_font: 0x05bf8c,
  start: 0,
  count: 100,
  scale: 8
}

OptionParser.new do |parser|
  parser.banner = "usage: render-original-text.rb --rom ROM --text-ids FILE --output-dir DIR"
  parser.on("--rom FILE") { |value| options[:rom] = value }
  parser.on("--text-ids FILE") { |value| options[:text_ids] = value }
  parser.on("--output-dir DIR") { |value| options[:output_dir] = value }
  parser.on("--single-font OFFSET") { |value| options[:single_font] = Integer(value) }
  parser.on("--extended-font OFFSET") { |value| options[:extended_font] = Integer(value) }
  parser.on("--start N", Integer) { |value| options[:start] = value }
  parser.on("--count N", Integer) { |value| options[:count] = value }
  parser.on("--scale N", Integer) { |value| options[:scale] = value }
end.parse!

required = %i[rom text_ids output_dir]
abort "missing required options" unless required.all? { |key| options[key] }
abort "count and scale must be positive" unless options[:count].positive? && options[:scale].positive?

rom = File.binread(options[:rom])
FileUtils.mkdir_p(options[:output_dir])

def glyph_rows(rom, glyph_id, single_font, extended_font)
  glyph_id &= 0x3fff
  if glyph_id <= 0xff
    return nil if glyph_id < 0x20
    words = rom.byteslice(single_font + (glyph_id - 0x20) * 26, 26)&.unpack("v13")
    abort "glyph 0x%04x outside ROM" % glyph_id unless words
    width, *rows = words
    abort "invalid width #{width} for glyph 0x%04x" % glyph_id unless (1..16).cover?(width)
    [width, rows]
  else
    rows = rom.byteslice(extended_font + (glyph_id - 0x100) * 24, 24)&.unpack("v12")
    abort "glyph 0x%04x outside ROM" % glyph_id unless rows
    [10, rows]
  end
end

selected = {}
File.foreach(options[:text_ids]).with_index do |line, line_index|
  next if line_index.zero?
  id, _length, units = line.chomp.split("\t", 3)
  numeric_id = Integer(id)
  next unless numeric_id.between?(options[:start], options[:start] + options[:count] - 1)
  selected[numeric_id] = units.to_s.split.map { |unit| Integer(unit, 16) }
end

selected.sort.each do |id, units|
  lines = [[]]
  units.each do |unit|
    if unit == 0x03
      lines << []
    elsif unit >= 0x20
      lines.last << unit
    end
  end

  rendered_lines = lines.map do |line|
    line.each_with_object([]) do |unit, glyphs|
      glyph = glyph_rows(rom, unit, options[:single_font], options[:extended_font])
      glyphs << glyph if glyph
    end
  end
  margin = options[:scale]
  line_gap = options[:scale]
  line_height = 12 * options[:scale]
  line_widths = rendered_lines.map do |glyphs|
    glyphs.sum { |width, _| (width + 1) * options[:scale] }
  end
  width = [line_widths.max.to_i + margin * 2, 64].max
  height = rendered_lines.length * line_height + (rendered_lines.length - 1) * line_gap + margin * 2
  pixels = Array.new(width * height, 255)

  rendered_lines.each_with_index do |glyphs, line_index|
    cursor_x = margin
    glyphs.each do |glyph_width, row_words|
      row_words.each_with_index do |word, y|
        glyph_width.times do |x|
          next if (word & (1 << (15 - x))).zero?
          options[:scale].times do |dy|
            options[:scale].times do |dx|
              pixel_x = cursor_x + x * options[:scale] + dx
              pixel_y = margin + line_index * (line_height + line_gap) + y * options[:scale] + dy
              pixels[pixel_y * width + pixel_x] = 0
            end
          end
        end
      end
      cursor_x += (glyph_width + 1) * options[:scale]
    end
  end

  File.open(File.join(options[:output_dir], "%05d.pgm" % id), "wb") do |file|
    file.write("P5\n#{width} #{height}\n255\n")
    file.write(pixels.pack("C*"))
  end
end

warn "rendered #{selected.length} strings to #{options[:output_dir]}"
