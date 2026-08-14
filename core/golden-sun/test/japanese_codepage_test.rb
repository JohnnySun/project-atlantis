# frozen_string_literal: true

require "minitest/autorun"
require_relative "../japanese_codepage"

class JapaneseCodepageTest < Minitest::Test
  def test_kana_boundary_entries
    mapping = GoldenSun::JapaneseCodepage.single_byte

    assert_equal "を", mapping.fetch(0x86)
    assert_equal "ヲ", mapping.fetch(0xa6)
    assert_equal "わ", mapping.fetch(0xfc)
    assert_equal "ん", mapping.fetch(0xfd)
  end
end
