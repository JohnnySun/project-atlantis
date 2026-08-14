# frozen_string_literal: true

require "minitest/autorun"
require_relative "../context_huffman"

class ContextHuffmanTest < Minitest::Test
  def test_keeps_two_tree_groups_for_original_codepage
    bundle = GoldenSun::ContextHuffman.build([[0x41, 0x142], [0x42]])

    assert_equal 2, bundle.fetch(:tree_groups).length
  end

  def test_adds_tree_group_for_extended_translation_glyphs
    bundle = GoldenSun::ContextHuffman.build([[0x234, 0x41]])
    third_group_offsets = bundle.fetch(:tree_groups).fetch(2).fetch(:offsets).unpack("v*")

    assert_equal 3, bundle.fetch(:tree_groups).length
    refute_equal 0x8000, third_group_offsets.fetch(0x34)
  end
end
