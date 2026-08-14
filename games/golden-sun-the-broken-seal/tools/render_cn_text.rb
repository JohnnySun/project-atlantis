#!/usr/bin/env ruby
# Render extracted Chinese text-ID rows as enlarged monochrome PGM images.

require "fileutils"

abort "usage: render_cn_text.rb ROM TEXT_IDS.tsv OUTPUT_DIR START COUNT" unless ARGV.length == 5
rom_path, text_path, output_dir, start_arg, count_arg = ARGV
start_id = Integer(start_arg)
count = Integer(count_arg)
rom = File.binread(rom_path)
FileUtils.mkdir_p(output_dir)

rows = {}
File.foreach(text_path).with_index do |line, index|
  next if index.zero?
  id, _length, units = line.chomp.split("\t", 3)
  numeric_id = Integer(id)
  next unless numeric_id.between?(start_id, start_id + count - 1)
  rows[numeric_id] = units.to_s.split.map { |unit| Integer(unit, 16) }
end

scale = 8
glyph_width = 16
glyph_height = 12
margin = 8
line_gap = 8

rows.sort.each do |id, units|
  lines = [[]]
  units.each do |unit|
    if unit == 0x03
      lines << []
    elsif unit < 0x20
      next
    else
      lines.last << unit
    end
  end
  lines = [[]] if lines.empty?

  width = [lines.map(&:length).max.to_i * glyph_width * scale + margin * 2, 64].max
  height = lines.length * glyph_height * scale + (lines.length - 1) * line_gap + margin * 2
  pixels = Array.new(width * height, 255)

  lines.each_with_index do |line, line_index|
    line.each_with_index do |glyph_id, glyph_index|
      glyph_offset = 0x870000 + glyph_id * 4
      abort "glyph 0x%04x outside ROM" % glyph_id if glyph_offset + 24 > rom.bytesize
      row_words = rom.byteslice(glyph_offset, 24).unpack("v12")
      origin_x = margin + glyph_index * glyph_width * scale
      origin_y = margin + line_index * (glyph_height * scale + line_gap)

      row_words.each_with_index do |word, y|
        glyph_width.times do |x|
          next if (word & (1 << (glyph_width - 1 - x))).zero?
          scale.times do |dy|
            scale.times do |dx|
              pixel_x = origin_x + x * scale + dx
              pixel_y = origin_y + y * scale + dy
              pixels[pixel_y * width + pixel_x] = 0
            end
          end
        end
      end
    end
  end

  output_path = File.join(output_dir, "%05d.pgm" % id)
  File.open(output_path, "wb") do |file|
    file.write("P5\n#{width} #{height}\n255\n")
    file.write(pixels.pack("C*"))
  end
end

warn "rendered #{rows.length} strings to #{output_dir}"
