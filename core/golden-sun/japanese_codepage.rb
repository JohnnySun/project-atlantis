# frozen_string_literal: true

require "unicode_normalize/normalize"

module GoldenSun
  module JapaneseCodepage
    module_function

    def single_byte
      @single_byte ||= begin
        mapping = (0x20..0x7e).to_h { |id| [id, id.chr(Encoding::UTF_8)] }
        assign(mapping, 0x87, "ぁぃぅぇぉゃゅょっ")
        assign(mapping, 0x91, "あいうえおかきくけこさしすせそ")
        mapping[0x86] = "を"
        mapping.merge!(0xa1 => "。", 0xa2 => "「", 0xa3 => "」", 0xa4 => "、", 0xa5 => "・")
        assign(mapping, 0xa6, "ヲァィゥェォャュョッーアイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワン゙゚")
        assign(mapping, 0xe0, "たちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわん")
        mapping.freeze
      end
    end

    def assign(mapping, first_id, characters)
      characters.each_char.with_index { |character, index| mapping[first_id + index] = character }
    end

    def load_extended(path)
      mapping = {}
      File.foreach(path).with_index do |line, index|
        next if index.zero?
        id, character, _status = line.chomp.split("\t", 3)
        numeric_id = Integer(id, 16)
        abort "duplicate Japanese codepage ID #{id}" if mapping.key?(numeric_id)
        abort "Japanese codepage entry #{id} must contain one character" unless character&.each_char&.count == 1
        mapping[numeric_id] = character
      end
      mapping
    end

    def decode(units, extended:, strict: false)
      text = units.map do |unit|
        if unit == 0x03
          "\n"
        elsif unit < 0x20
          "{%02X}" % unit
        else
          character = single_byte[unit] || extended[unit]
          abort "unmapped Japanese code unit: 0x%03x" % unit if strict && !character
          character || "{U+%03X}" % unit
        end
      end.join
      text.unicode_normalize(:nfc)
    end
  end
end
