#!/usr/bin/env ruby

FORBIDDEN_EXTENSIONS = %w[
  .gba .agb .rom .sav .srm .state .zip .7z .rar .bps .ips .ups
].freeze
MAX_FILE_SIZE = 10 * 1024 * 1024

paths = `git ls-files -co --exclude-standard -z`.split("\0")
problems = []

paths.each do |path|
  next unless File.file?(path)

  extension = File.extname(path).downcase
  problems << "forbidden binary/archive: #{path}" if FORBIDDEN_EXTENSIONS.include?(extension)
  problems << "file exceeds 10 MiB: #{path}" if File.size(path) > MAX_FILE_SIZE
end

if problems.empty?
  puts "repository safety check passed (#{paths.length} visible files)"
  exit 0
end

warn problems.join("\n")
exit 1

