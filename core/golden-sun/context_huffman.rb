# frozen_string_literal: true

module GoldenSun
  module ContextHuffman
    Node = Struct.new(:frequency, :sequence, :value, :left, :right) do
      def leaf?
        !value.nil?
      end
    end

    class BitWriter
      def initialize
        @bytes = +""
        @bytes.force_encoding(Encoding::BINARY)
        @value = 0
        @count = 0
      end

      def write(bit)
        @value |= (bit & 1) << @count
        @count += 1
        flush_byte if @count == 8
      end

      def finish
        flush_byte unless @count.zero?
        @bytes
      end

      private

      def flush_byte
        @bytes << @value
        @value = 0
        @count = 0
      end
    end

    module_function

    def build(strings)
      frequencies = Hash.new { |hash, key| hash[key] = Hash.new(0) }
      first_seen = Hash.new { |hash, key| hash[key] = {} }
      sequence = 0

      strings.each do |values|
        previous = 0
        (values + [0]).each do |value|
          abort "character outside 12-bit range: 0x%x" % value unless value.between?(0, 0xfff)
          frequencies[previous][value] += 1
          unless first_seen[previous].key?(value)
            first_seen[previous][value] = sequence
            sequence += 1
          end
          previous = value
        end
      end

      roots = {}
      codes = {}
      frequencies.each do |previous, counts|
        queue = counts.map do |value, frequency|
          Node.new(frequency, first_seen[previous][value], value, nil, nil)
        end
        next_sequence = sequence
        while queue.length > 1
          queue.sort_by! { |node| [node.frequency, node.sequence] }
          left = queue.shift
          right = queue.shift
          queue << Node.new(left.frequency + right.frequency, next_sequence, nil, left, right)
          next_sequence += 1
        end
        roots[previous] = queue.first
        codes[previous] = {}
        assign_codes(queue.first, [], codes[previous])
      end

      highest_context = frequencies.keys.max || 0
      tree_group_count = [2, (highest_context >> 8) + 1].max
      tree_groups = tree_group_count.times.map { |group| build_tree_group(group, roots) }
      text_blocks = []
      strings.each_slice(256) do |block_strings|
        data = +""
        data.force_encoding(Encoding::BINARY)
        lengths = +""
        lengths.force_encoding(Encoding::BINARY)
        block_strings.each do |values|
          writer = BitWriter.new
          previous = 0
          (values + [0]).each do |value|
            code = codes.fetch(previous).fetch(value)
            code.each { |bit| writer.write(bit) }
            previous = value
          end
          encoded = writer.finish
          data << encoded
          remaining = encoded.bytesize
          while remaining > 0xfe
            lengths << 0xff
            remaining -= 0xff
          end
          lengths << remaining
        end
        text_blocks << { data: data, lengths: lengths }
      end

      { tree_groups: tree_groups, text_blocks: text_blocks }
    end

    def assign_codes(node, prefix, output)
      if node.leaf?
        output[node.value] = prefix
        return
      end
      assign_codes(node.left, prefix + [0], output)
      assign_codes(node.right, prefix + [1], output)
    end

    def build_tree_group(group, roots)
      data = +""
      data.force_encoding(Encoding::BINARY)
      offsets = Array.new(256, 0x8000)

      256.times do |low|
        previous = (group << 8) | low
        root = roots[previous]
        next unless root

        leaves = []
        tree_writer = BitWriter.new
        serialize_tree(root, tree_writer, leaves)
        leaf_data = pack_leaves(leaves)
        relative = data.bytesize + leaf_data.bytesize
        abort "Huffman tree group #{group} exceeds 15-bit offsets" if relative >= 0x8000
        offsets[low] = relative
        data << leaf_data << tree_writer.finish
      end

      { data: data, offsets: offsets.pack("v*") }
    end

    def serialize_tree(node, writer, leaves)
      if node.leaf?
        writer.write(1)
        leaves << node.value
      else
        writer.write(0)
        serialize_tree(node.left, writer, leaves)
        serialize_tree(node.right, writer, leaves)
      end
    end

    def pack_leaves(leaves)
      size = (leaves.length * 12 + 7) / 8
      bytes = Array.new(size, 0)
      tree_offset = size
      leaves.each_with_index do |value, leaf_id|
        packed_offset = leaf_id + (leaf_id >> 1)
        pointer = tree_offset - packed_offset
        if leaf_id.odd?
          bytes[pointer - 1] = (bytes[pointer - 1] & 0xf0) | ((value >> 8) & 0x0f)
          bytes[pointer - 2] = value & 0xff
        else
          bytes[pointer - 1] = (value >> 4) & 0xff
          bytes[pointer - 2] = (bytes[pointer - 2] & 0x0f) | ((value & 0x0f) << 4)
        end
      end
      bytes.pack("C*")
    end
  end
end
