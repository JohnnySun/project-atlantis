#!/usr/bin/env ruby
# frozen_string_literal: true

require "json"
require "optparse"
require_relative "japanese_codepage"

options = {}
OptionParser.new do |parser|
  parser.banner = "usage: decode-text-ids.rb --text-ids TSV --codepage TSV --output JSONL"
  parser.on("--text-ids FILE") { |value| options[:text_ids] = value }
  parser.on("--codepage FILE") { |value| options[:codepage] = value }
  parser.on("--output FILE") { |value| options[:output] = value }
end.parse!

required = %i[text_ids codepage output]
abort "missing required options" unless required.all? { |key| options[key] }

extended = GoldenSun::JapaneseCodepage.load_extended(options[:codepage])
count = 0
File.open(options[:output], "w") do |output|
  File.foreach(options[:text_ids]).with_index do |line, index|
    next if index.zero?
    id, _length, encoded = line.chomp.split("\t", 3)
    units = encoded.to_s.split.map { |unit| Integer(unit, 16) }
    text = GoldenSun::JapaneseCodepage.decode(units, extended: extended, strict: true)
    output.puts JSON.generate(id: Integer(id), locale: "ja", text: text)
    count += 1
  end
end

warn "decoded #{count} strings to #{options[:output]}"
