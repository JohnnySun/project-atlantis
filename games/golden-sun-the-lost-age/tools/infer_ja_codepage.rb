#!/usr/bin/env ruby
# frozen_string_literal: true

require "unicode_normalize/normalize"
require_relative "../../../core/golden-sun/japanese_codepage"

text_ids_path, ocr_path = ARGV
abort "usage: infer_ja_codepage.rb TEXT_IDS.tsv OCR_RESULTS.tsv" unless ARGV.length == 2

map = GoldenSun::JapaneseCodepage.single_byte

units_by_id = {}
File.foreach(text_ids_path).with_index do |line, index|
  next if index.zero?
  id, _, units = line.chomp.split("\t", 3)
  units_by_id[Integer(id)] = units.split.map { |unit| Integer(unit, 16) }.select { |unit| unit >= 0x20 }
end

ocr_by_id = {}
File.foreach(ocr_path) do |line|
  path, text = line.chomp.split("\t", 2)
  next unless path && text
  ocr_by_id[File.basename(path, ".pgm").to_i] = text.gsub("\\n", "")
end

def normalized_chars(text)
  text.unicode_normalize(:nfkd).chars.reject { |char| char.match?(/\s/) }
end

def cjk?(char)
  cp = char.ord
  (0x3400..0x9fff).cover?(cp) || (0xf900..0xfaff).cover?(cp)
end

votes = Hash.new { |hash, key| hash[key] = Hash.new(0) }
accepted = 0
ocr_by_id.each do |id, text|
  units = units_by_id[id]
  next unless units
  source = units.flat_map do |unit|
    known = map[unit]
    known ? normalized_chars(known).map { |char| [unit, char] } : [[unit, nil]]
  end
  target = normalized_chars(text)
  n = source.length
  m = target.length
  cost = Array.new(n + 1) { Array.new(m + 1, Float::INFINITY) }
  back = Array.new(n + 1) { Array.new(m + 1) }
  cost[0][0] = 0.0
  (0..n).each do |i|
    (0..m).each do |j|
      current = cost[i][j]
      if i < n && current + 1 < cost[i + 1][j]
        cost[i + 1][j] = current + 1
        back[i + 1][j] = [i, j, :delete]
      end
      if j < m && current + 1 < cost[i][j + 1]
        cost[i][j + 1] = current + 1
        back[i][j + 1] = [i, j, :insert]
      end
      next unless i < n && j < m
      known = source[i][1]
      substitution = if known == target[j]
        0.0
      elsif known.nil? && cjk?(target[j])
        0.15
      elsif known.nil?
        0.8
      else
        1.5
      end
      if current + substitution < cost[i + 1][j + 1]
        cost[i + 1][j + 1] = current + substitution
        back[i + 1][j + 1] = [i, j, :substitute]
      end
    end
  end
  quality = cost[n][m] / [n, m, 1].max
  next if quality > 0.32
  accepted += 1
  pairs = []
  i = n
  j = m
  while i.positive? || j.positive?
    previous = back[i][j]
    break unless previous
    pi, pj, action = previous
    pairs << [source[pi], target[pj]] if action == :substitute
    i = pi
    j = pj
  end
  pairs.each do |(unit, known), character|
    votes[unit][character] += 1 if known.nil? && cjk?(character)
  end
end

warn "accepted OCR lines: #{accepted}/#{ocr_by_id.length}"
puts "id\tcandidates"
votes.sort.each do |unit, counts|
  ranked = counts.sort_by { |character, count| [-count, character] }.first(8)
  puts "%04x\t%s" % [unit, ranked.map { |character, count| "#{character}:#{count}" }.join(" ")]
end
