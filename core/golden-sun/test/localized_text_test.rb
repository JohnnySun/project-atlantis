# frozen_string_literal: true

require "minitest/autorun"
require_relative "../localized_text"

class LocalizedTextTest < Minitest::Test
  def test_encodes_internal_controls_and_newlines
    glyph_ids = { "造" => 0x198, "成" => 0x199, "點" => 0x19a }

    assert_equal [0x12, 0x198, 0x199, 0x03, 0x16, 0x19a],
      GoldenSun::LocalizedText.encode("{12}造成\n{16}點", glyph_ids)
  end

  def test_reports_controls_in_translation_order
    assert_equal [0x12, 0x03, 0x16],
      GoldenSun::LocalizedText.controls("{12}造成\n{16}點")
  end

  def test_rejects_non_control_markers
    error = assert_raises(ArgumentError) do
      GoldenSun::LocalizedText.tokens("{20}")
    end

    assert_match(/outside 0x00-0x1f/, error.message)
  end
end
