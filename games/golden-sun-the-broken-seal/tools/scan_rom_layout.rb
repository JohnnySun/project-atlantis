#!/usr/bin/env ruby
# Read-only structural scanner for GBA ROM pointer tables and modified ranges.

abort "usage: scan_rom_layout.rb ROM [REFERENCE_ROM]" unless (1..2).cover?(ARGV.length)

rom_path, reference_path = ARGV
rom = File.binread(rom_path)

def rom_pointer?(value, rom_size)
  value >= 0x08000000 && value < 0x08000000 + rom_size
end

puts "ROM: #{rom_path}"
puts "size: #{rom.bytesize} (0x#{rom.bytesize.to_s(16)})"
puts
puts "Aligned GBA-pointer runs (at least 8 pointers):"

offset = 0
while offset + 4 <= rom.bytesize
  value = rom.byteslice(offset, 4).unpack1("V")
  unless rom_pointer?(value, rom.bytesize)
    offset += 4
    next
  end

  start = offset
  values = []
  while offset + 4 <= rom.bytesize
    value = rom.byteslice(offset, 4).unpack1("V")
    break unless rom_pointer?(value, rom.bytesize)
    values << value
    offset += 4
  end

  if values.length >= 8
    targets = values.map { |pointer| pointer - 0x08000000 }
    puts "  0x%06x..0x%06x  count=%-5d targets=0x%06x..0x%06x" % [
      start, offset - 1, values.length, targets.min, targets.max
    ]
  end

  offset += 4 if offset == start
end

exit unless reference_path

reference = File.binread(reference_path)
common_size = [rom.bytesize, reference.bytesize].min
ranges = []
cursor = 0

while cursor < common_size
  if rom.getbyte(cursor) == reference.getbyte(cursor)
    cursor += 1
    next
  end

  start = cursor
  cursor += 1 while cursor < common_size && rom.getbyte(cursor) != reference.getbyte(cursor)
  ranges << [start, cursor - 1]
end

puts
puts "Byte-difference summary versus #{reference_path}:"
puts "  differing runs: #{ranges.length}"
puts "  differing bytes in common range: #{ranges.sum { |start, finish| finish - start + 1 }}"
puts "  appended bytes: #{[rom.bytesize - common_size, 0].max}"

bucket_size = 0x10000
buckets = Hash.new(0)
ranges.each do |start, finish|
  first_bucket = start / bucket_size
  last_bucket = finish / bucket_size
  (first_bucket..last_bucket).each do |bucket|
    bucket_start = bucket * bucket_size
    overlap_start = [start, bucket_start].max
    overlap_end = [finish, bucket_start + bucket_size - 1].min
    buckets[bucket] += overlap_end - overlap_start + 1
  end
end

puts "  changed 64 KiB buckets (top 30):"
buckets.sort_by { |_, count| -count }.first(30).each do |bucket, count|
  puts "    0x%06x..0x%06x  %5d bytes (%5.1f%%)" % [
    bucket * bucket_size,
    (bucket + 1) * bucket_size - 1,
    count,
    count * 100.0 / bucket_size
  ]
end
