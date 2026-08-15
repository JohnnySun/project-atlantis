#!/usr/bin/env ruby
# GS1 (AGSJ01) counterpart to golden-sun-the-lost-age/tools/build_zh_tw_trial.rb.
#
# Differs from the GS2 builder in three structural ways:
# - The commercial ROM is only 8 MiB with no usable blank tail, so the input
#   here is an already-expanded ROM (see tools/expand_rom.rb) and
#   insert_offset sits at the original 0x800000 boundary.
# - Every pointer role (font/huffman/text) was found at more than one
#   literal-pool location during reverse engineering (two live code paths
#   each -- see research/jp-codepage-derivation.md and the game README for
#   the disassembly evidence) except text, which had one. All literal sites
#   for a role must be patched, or the unpatched code path keeps reading the
#   stale table and produces a path-dependent bug.
# - original_extended_count is 114 (this game's own derived codepage), not
#   GS2's 152.

require "optparse"
require "json"
require_relative "../../../core/golden-sun/context_huffman"
require_relative "../../../core/golden-sun/japanese_codepage"
require_relative "../../../core/golden-sun/localized_text"

options = {
  insert_offset: 0x800000,
  original_extended_font: 0x33b30,
  original_extended_count: 114,
  translations: [],
  font_pointer_literals: [0x157e4, 0x179a0],
  huffman_pointer_literals: [0x1556c, 0x19d04],
  text_pointer_literals: [0x155cc]
}

OptionParser.new do |parser|
  parser.banner = "usage: build_zh_tw_trial.rb --rom ROM --text-ids TSV --codepage TSV --translations JSONL [--translations JSONL ...] --bdf FONT.bdf --output ROM"
  parser.on("--rom FILE") { |value| options[:rom] = value }
  parser.on("--text-ids FILE") { |value| options[:text_ids] = value }
  parser.on("--codepage FILE") { |value| options[:codepage] = value }
  parser.on("--translations FILE", "repeat for additional translation batches") do |value|
    options[:translations] << value
  end
  parser.on("--bdf FILE") { |value| options[:bdf] = value }
  parser.on("--output FILE") { |value| options[:output] = value }
end.parse!

required = %i[rom text_ids codepage bdf output]
abort "missing required options" unless required.all? { |key| options[key] }
abort "missing required options" if options[:translations].empty?

rom = File.binread(options[:rom])
abort "expected a ROM larger than 8 MiB (pre-expand with tools/expand_rom.rb)" unless rom.bytesize > 8 * 1024 * 1024
abort "insertion area is not blank" unless rom.byteslice(options[:insert_offset], rom.bytesize - options[:insert_offset]).bytes.all?(&:zero?)

strings = []
File.foreach(options[:text_ids]).with_index do |line, index|
  next if index.zero?
  id, _length, units = line.chomp.split("\t", 3)
  abort "non-sequential string ID #{id}" unless Integer(id) == strings.length
  strings << units.to_s.split.map { |unit| Integer(unit, 16) }
end
abort "expected 11,115 strings" unless strings.length == 11_115

source_codepage = GoldenSun::JapaneseCodepage.load_extended(options[:codepage])
trial_strings = {}
options[:translations].each do |translations_path|
  File.foreach(translations_path).with_index(1) do |line, line_number|
    next if line.strip.empty?
    record = JSON.parse(line)
    location = "#{translations_path}:#{line_number}"
    abort "unexpected game at #{location}" unless record.fetch("game") == "golden-sun-the-broken-seal"
    abort "unexpected revision at #{location}" unless record.fetch("revision") == "AGSJ01-rev0"
    id = Integer(record.fetch("string_id"))
    abort "translation ID outside extracted text: #{id}" unless id.between?(0, strings.length - 1)
    abort "duplicate translation ID: #{id}" if trial_strings.key?(id)

    original = strings.fetch(id)
    decoded_source = GoldenSun::JapaneseCodepage.decode(original, extended: source_codepage, strict: true)
      .gsub(/\{[0-9A-F]{2}\}/, "")
    abort "Japanese source mismatch for translation ID #{id}" unless record.fetch("source").fetch("text") == decoded_source
    declared_controls = record.dig("context", "control_codes") || []
    actual_controls = original.select { |unit| unit < 0x20 }.map { |unit| "%04x" % unit }
    abort "control-code mismatch for translation ID #{id}" unless declared_controls == actual_controls

    first_display = original.index { |unit| unit >= 0x20 }
    last_display = original.rindex { |unit| unit >= 0x20 }
    abort "translation ID #{id} has no display text" unless first_display && last_display
    target_text = record.fetch("targets").fetch("zh-TW").fetch("text")
    if GoldenSun::LocalizedText.explicit_controls?(target_text)
      target_controls = GoldenSun::LocalizedText.controls(target_text).map { |unit| "%04x" % unit }
      abort "translated control-code mismatch for translation ID #{id}" unless target_controls == actual_controls
      trial_strings[id] = { text: target_text, prefix: [], suffix: [] }
    else
      internal_controls = original[first_display..last_display].select { |unit| unit < 0x20 && unit != 0x03 }
      abort "translation ID #{id} needs explicit internal control markers" unless internal_controls.empty?

      prefix = original[0...first_display].reject { |unit| unit == 0x03 }
      suffix = original[(last_display + 1)..].reject { |unit| unit == 0x03 }
      target_controls = (prefix + GoldenSun::LocalizedText.controls(target_text) + suffix)
        .map { |unit| "%04x" % unit }
      abort "translated control-code mismatch for translation ID #{id}" unless target_controls == actual_controls
      trial_strings[id] = { text: target_text, prefix: prefix, suffix: suffix }
    end
  end
end
abort "translation files are empty" if trial_strings.empty?

new_glyph_ids = {}
trial_strings.each_value do |trial|
  GoldenSun::LocalizedText.display_characters(trial.fetch(:text)).each do |character|
    next if character.ord.between?(0x20, 0x7e)
    new_glyph_ids[character] ||= options[:original_extended_count] + 0x100 + new_glyph_ids.length
  end
end
trial_strings.each do |id, trial|
  strings[id] = trial.fetch(:prefix) +
    GoldenSun::LocalizedText.encode(trial.fetch(:text), new_glyph_ids) +
    trial.fetch(:suffix)
end

def read_bdf(path, wanted)
  glyphs = {}
  current = nil
  bitmap = nil
  in_bitmap = false
  File.foreach(path) do |line|
    line = line.strip
    if line.start_with?("STARTCHAR ")
      current = { encoding: nil, bbx: nil }
      bitmap = []
    elsif current && line.start_with?("ENCODING ")
      current[:encoding] = Integer(line.split.last)
    elsif current && line.start_with?("BBX ")
      current[:bbx] = line.split.drop(1).map(&:to_i)
    elsif current && line == "BITMAP"
      in_bitmap = true
    elsif current && line == "ENDCHAR"
      if wanted.include?(current[:encoding])
        abort "trial glyph must use a 10x10 BDF box" unless current[:bbx]&.first(2) == [10, 10]
        glyphs[current[:encoding]] = bitmap.map { |row| Integer(row, 16) }
      end
      current = nil
      in_bitmap = false
    elsif current && in_bitmap
      bitmap << line
    end
  end
  glyphs
end

codepoints = new_glyph_ids.keys.map(&:ord)
bdf_glyphs = read_bdf(options[:bdf], codepoints)
missing = codepoints.reject { |codepoint| bdf_glyphs.key?(codepoint) }
abort "missing BDF glyphs: #{missing.map { |value| "U+%04X" % value }.join(" ")}" unless missing.empty?

extended_font = rom.byteslice(options[:original_extended_font], options[:original_extended_count] * 24).dup
new_glyph_ids.sort_by { |_, glyph_id| glyph_id }.each do |character, glyph_id|
  abort "non-contiguous trial glyph IDs" unless glyph_id == 0x100 + extended_font.bytesize / 24
  rows = [0] + bdf_glyphs.fetch(character.ord) + [0]
  extended_font << rows.pack("v*")
end

huffman = GoldenSun::ContextHuffman.build(strings)
bundle = +""
bundle.force_encoding(Encoding::BINARY)
layout = {}

append = lambda do |name, bytes, alignment = 4|
  padding = (-bundle.bytesize) % alignment
  bundle << ("\0" * padding)
  layout[name] = options[:insert_offset] + bundle.bytesize
  bundle << bytes
end

append.call(:font, extended_font)
huffman[:tree_groups].each_with_index do |group, index|
  append.call("tree_data_#{index}".to_sym, group[:data])
  append.call("tree_offsets_#{index}".to_sym, group[:offsets], 2)
end

huffman[:text_blocks].each_with_index do |block, index|
  append.call("text_data_#{index}".to_sym, block[:data])
  append.call("text_lengths_#{index}".to_sym, block[:lengths])
end

pointer = ->(offset) { 0x08000000 + offset }
huffman_table = huffman[:tree_groups].each_index.flat_map do |index|
  [pointer.call(layout.fetch("tree_data_#{index}".to_sym)), pointer.call(layout.fetch("tree_offsets_#{index}".to_sym))]
end.pack("V*")
append.call(:huffman_table, huffman_table)

text_table = huffman[:text_blocks].each_index.flat_map do |index|
  [pointer.call(layout.fetch("text_data_#{index}".to_sym)), pointer.call(layout.fetch("text_lengths_#{index}".to_sym))]
end.pack("V*")
append.call(:text_table, text_table)

abort "trial data exceeds blank ROM tail" if options[:insert_offset] + bundle.bytesize > rom.bytesize
rom[options[:insert_offset], bundle.bytesize] = bundle

font_pointer = [pointer.call(layout.fetch(:font))].pack("V")
huffman_pointer = [pointer.call(layout.fetch(:huffman_table))].pack("V")
text_pointer = [pointer.call(layout.fetch(:text_table))].pack("V")
options[:font_pointer_literals].each { |offset| rom[offset, 4] = font_pointer }
options[:huffman_pointer_literals].each { |offset| rom[offset, 4] = huffman_pointer }
options[:text_pointer_literals].each { |offset| rom[offset, 4] = text_pointer }

File.binwrite(options[:output], rom)

warn "built zh-TW trial ROM: #{options[:output]}"
warn "inserted #{bundle.bytesize} bytes at 0x%06x" % options[:insert_offset]
warn "translated IDs: #{trial_strings.keys.sort.length} (range #{trial_strings.keys.min}-#{trial_strings.keys.max})"
warn "trial glyph IDs: #{new_glyph_ids.map { |character, id| "#{character}=0x%03x" % id }.join(" ")}"
warn "extended font pointer: 0x%08x (patched at #{options[:font_pointer_literals].map { |o| "0x%06x" % o }.join(", ")})" % pointer.call(layout.fetch(:font))
warn "Huffman pointer table: 0x%08x (patched at #{options[:huffman_pointer_literals].map { |o| "0x%06x" % o }.join(", ")})" % pointer.call(layout.fetch(:huffman_table))
warn "text pointer table: 0x%08x (patched at #{options[:text_pointer_literals].map { |o| "0x%06x" % o }.join(", ")})" % pointer.call(layout.fetch(:text_table))
