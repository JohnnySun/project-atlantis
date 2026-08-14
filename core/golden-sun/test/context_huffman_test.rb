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

  def test_adds_fourth_tree_group_after_0x2ff
    bundle = GoldenSun::ContextHuffman.build([[0x30d, 0x41]])
    fourth_group_offsets = bundle.fetch(:tree_groups).fetch(3).fetch(:offsets).unpack("v*")

    assert_equal 4, bundle.fetch(:tree_groups).length
    refute_equal 0x8000, fourth_group_offsets.fetch(0x0d)
  end

  def test_adds_fifth_tree_group_after_0x3ff
    bundle = GoldenSun::ContextHuffman.build([[0x40d, 0x41]])
    fifth_group_offsets = bundle.fetch(:tree_groups).fetch(4).fetch(:offsets).unpack("v*")

    assert_equal 5, bundle.fetch(:tree_groups).length
    refute_equal 0x8000, fifth_group_offsets.fetch(0x0d)
  end

  def test_adds_sixth_tree_group_after_0x4ff
    bundle = GoldenSun::ContextHuffman.build([[0x50d, 0x41]])
    sixth_group_offsets = bundle.fetch(:tree_groups).fetch(5).fetch(:offsets).unpack("v*")

    assert_equal 6, bundle.fetch(:tree_groups).length
    refute_equal 0x8000, sixth_group_offsets.fetch(0x0d)
  end
end
