# frozen_string_literal: true

module GoldenSun
  module LocalizedText
    CONTROL_MARKER = /\{([0-9A-Fa-f]{2})\}/

    module_function

    def explicit_controls?(text)
      text.match?(CONTROL_MARKER)
    end

    def tokens(text)
      output = []
      offset = 0
      while offset < text.length
        remainder = text[offset..]
        marker = CONTROL_MARKER.match(remainder)
        if marker&.begin(0) == 0
          value = Integer(marker[1], 16)
          raise ArgumentError, "control marker outside 0x00-0x1f: #{marker[0]}" unless value < 0x20

          output << value
          offset += marker[0].length
          next
        end

        character = remainder.each_char.first
        output << (character == "\n" ? 0x03 : character)
        offset += 1
      end
      output
    end

    def controls(text)
      tokens(text).select { |token| token.is_a?(Integer) }
    end

    def display_characters(text)
      tokens(text).select { |token| token.is_a?(String) }
    end

    def encode(text, glyph_ids)
      tokens(text).map do |token|
        next token if token.is_a?(Integer)
        next token.ord if token.ord.between?(0x20, 0x7e)

        glyph_ids.fetch(token)
      end
    end
  end
end
