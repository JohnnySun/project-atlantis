#!/usr/bin/env ruby
# Render 2024 Chinese font glyph IDs to a PPM contact sheet for inspection/OCR.

abort "usage: render_cn_glyphs.rb ROM OUTPUT.ppm ID..." if ARGV.length < 3
rom_path, output_path, *id_args = ARGV
rom = File.binread(rom_path)
ids = id_args.map { |value| Integer(value, 16) }

glyph_width = 16
glyph_height = 12
scale = 4
columns = [ids.length, 8].min
rows = (ids.length.to_f / columns).ceil
cell_width = glyph_width * scale
cell_height = glyph_height * scale
width = columns * cell_width
height = rows * cell_height
pixels = Array.new(width * height * 3, 255)

ids.each_with_index do |glyph_id, index|
  glyph_offset = 0x870000 + glyph_id * 4
  abort "glyph 0x%04x outside ROM" % glyph_id if glyph_offset + 24 > rom.bytesize
  row_words = rom.byteslice(glyph_offset, 24).unpack("v12")
  origin_x = (index % columns) * cell_width
  origin_y = (index / columns) * cell_height

  row_words.each_with_index do |word, y|
    glyph_width.times do |x|
      next if (word & (1 << (glyph_width - 1 - x))).zero?
      scale.times do |dy|
        scale.times do |dx|
          pixel_x = origin_x + x * scale + dx
          pixel_y = origin_y + y * scale + dy
          position = (pixel_y * width + pixel_x) * 3
          pixels[position, 3] = [0, 0, 0]
        end
      end
    end
  end
end

File.open(output_path, "wb") do |file|
  file.write("P6\n#{width} #{height}\n255\n")
  file.write(pixels.pack("C*"))
end

warn "rendered #{ids.length} glyphs to #{output_path}"
