#!/usr/bin/env ruby

require "optparse"
require "set"
require "zlib"

options = {}
OptionParser.new do |parser|
  parser.banner = "usage: extract-unifont-subset.rb --font FONT.hex[.gz] --output SUBSET.hex TEXT..."
  parser.on("--font PATH", "Unifont .hex or .hex.gz source") { |path| options[:font] = path }
  parser.on("--output PATH", "output Unifont .hex subset") { |path| options[:output] = path }
end.parse!

abort "missing --font" unless options[:font]
abort "missing --output" unless options[:output]
abort "provide at least one UTF-8 text file" if ARGV.empty?

codepoints = Set.new
ARGV.each do |path|
  File.read(path, encoding: "UTF-8").each_codepoint do |codepoint|
    next if [0x09, 0x0a, 0x0d].include?(codepoint)

    codepoints << codepoint
  end
end

glyphs = {}
reader = if options[:font].end_with?(".gz")
           Zlib::GzipReader.open(options[:font])
         else
           File.open(options[:font], "r")
         end

reader.each_line do |line|
  codepoint_hex, bitmap = line.strip.split(":", 2)
  next unless bitmap

  codepoint = Integer(codepoint_hex, 16)
  glyphs[codepoint] = "#{codepoint_hex}:#{bitmap}" if codepoints.include?(codepoint)
end
reader.close

missing = codepoints.reject { |codepoint| glyphs.key?(codepoint) }.sort
File.open(options[:output], "w") do |file|
  codepoints.sort.each do |codepoint|
    file.puts glyphs.fetch(codepoint) if glyphs.key?(codepoint)
  end
end

warn "selected #{glyphs.length} glyphs; missing #{missing.length}"
unless missing.empty?
  warn "missing codepoints: #{missing.map { |codepoint| "U+%04X" % codepoint }.join(" ")}"
  exit 1
end
