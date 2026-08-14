#!/usr/bin/env ruby
# frozen_string_literal: true

require "json"

source_path, built_path, translations_path = ARGV
abort "usage: verify_text_delta.rb SOURCE.tsv BUILT.tsv TRANSLATIONS.jsonl" unless ARGV.length == 3

source_lines = File.readlines(source_path, chomp: true)
built_lines = File.readlines(built_path, chomp: true)
abort "text TSV line counts differ" unless source_lines.length == built_lines.length

expected_ids = File.readlines(translations_path, chomp: true)
  .reject(&:empty?)
  .map { |line| Integer(JSON.parse(line).fetch("string_id")) }
abort "duplicate translation IDs" unless expected_ids.uniq.length == expected_ids.length
expected_ids.sort!

actual_ids = []
source_lines.zip(built_lines).each_with_index do |(source, built), line_number|
  actual_ids << line_number - 1 if source != built
end

unless actual_ids == expected_ids
  missing = expected_ids - actual_ids
  unexpected = actual_ids - expected_ids
  abort "text delta mismatch: missing=#{missing.join(",")} unexpected=#{unexpected.join(",")}"
end

puts "verified #{actual_ids.length} translated IDs: #{actual_ids.join(" ")}"
