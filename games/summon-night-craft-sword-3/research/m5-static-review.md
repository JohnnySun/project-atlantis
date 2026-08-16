# M5 static translation review boundary

## Review scope

This is the first language/term/font/layout review of the eight existing
bounded records. It does not add a target, change a ledger status, or claim
runtime/release readiness. Every row remains `zh-TW`/`ai_draft` until human
approval and runtime gates are available.

The review uses the ignored B3CJ source table only through stable ID, source
hash, provenance, and bounded control metadata. No Japanese source sentence is
copied into this tracked report.

## Semantic and terminology review

| string_id | source_hash | current target | static semantic review | term decision |
| --- | --- | --- | --- | --- |
| `b3cj:t2:024:0x0064` | `c10caff6b389dc1506d1879cdac4e21111ead7eb8b41e05eca6aed3d73873ddc` | `這次的獎品是…` | Generic prize-header meaning and Taiwan Traditional forms are consistent with the repeated group. | `獎品` remains provisional glossary term. |
| `b3cj:t2:022:0x004e` | `956b323686afadc76cb837332e29e5a92db3d88a746c54f25a23d9a19b1d4f2c` | `劈柴新手　　` | Rank/label reading is semantically plausible; explicit padding is layout-only. | `劈柴` remains provisional generic action term. |
| `b3cj:t2:016:0x001e` | `0c7840a194483b36af7414a8e8624c93d3a3ae62e6167eb1040daaae317e33d8` | `警告！　　` | Generic warning label is a direct Taiwan Traditional UI rendering. | `警告` remains provisional generic UI term. |
| `b3cj:t2:025:0x0b6e` | `edfe7b0a4cfae39281960bcfeb2592b66bbd47136d6b29c1bc2082dc5cf8e2c9` | `嗯…　　` | Intent is a hesitation/ellipsis utterance; `嗯…` is readable but `呃…`/`那個…` may be more idiomatic, so language approval is still required. | `dialogue.ellipsis_ack` remains provisional. |
| `b3cj:t2:024:0x0078` | `cd5eb4f2833b81100caa4feb0ddd9a3a1d9ffeefa6f60fdf1a2a18ce3f33b329` | `特獎　重金礦` | Award label is plausible; the ore name may be an in-game item term and is not externally verified. | `特獎` provisional; `重金礦` is `blocked_external_lookup` in the glossary. |
| `b3cj:t2:024:0x012c` | `c10caff6b389dc1506d1879cdac4e21111ead7eb8b41e05eca6aed3d73873ddc` | `這次的獎品是…` | Matches the first and third occurrences exactly; consistency pass at static language level. | Reuses provisional `獎品`. |
| `b3cj:t2:024:0x0886` | `0d5a78457208e290171e1080982d81302880952077c85746ab7ca5003d098976` | `要抽獎嗎？　　` | Generic yes/no lottery question is natural zh-TW; explicit padding is layout-only. | `抽獎` provisional generic activity term; new `嗎` glyph is statically proven. |
| `b3cj:t2:024:0x01f0` | `c10caff6b389dc1506d1879cdac4e21111ead7eb8b41e05eca6aed3d73873ddc` | `這次的獎品是…` | Matches the first and second occurrences exactly; consistency pass at static language level. | Reuses provisional `獎品`. |

The external terminology lookup for `重金礦` was attempted through the
Wikipedia zh-tw API and Bahamut search endpoint, but WebSearch returned a
network error and both read-only curl attempts failed DNS resolution. The
elevated retry was rejected by the execution safety reviewer. This is an
external research limitation, not evidence that either candidate spelling is
canonical; the item remains unapproved.

## Font and layout review

- The shared static font base remains `0x14d5c88`, with 12×12 active pixels in
  24-byte cells. All eight target payloads use one line and their declared
  `max_width`/byte contracts; full-width padding is preserved rather than
  treated as terminator data.
- The existing extension mapping is unchanged: `ec64→0x847` (這),
  `ec65→0x848` (獎), `ec66→0x849` (是), `ec67→0x84a` (劈),
  `ec6c→0x84b` (柴), `ec6d→0x84c` (嗯), `ec6e→0x84d` (礦), and
  `ec6f→0x84e` (嗎). All are within the fail-closed `0x845..0x85f`
  allocation range; no fallback or duplicate allocation is accepted.
- Static cell/render hashes and adjacent untouched-glyph hashes are recorded
  in the M2.5, M4.1, M4.3, M5.2, M5.4, and M5.5 receipts. M5.5 additionally
  proves all four inherited mappings (`ec64/ec65/ec66/ec6f`) unchanged from
  the M5.4 cumulative ROM.
- All eight records have `0x0308`/`0x0000` text controls and no opaque control
  in the selected payloads. The following control shapes are retained by each
  builder; no unknown VM semantics were guessed.

## Gate result

Static semantic review: `7 provisional-pass`, `1 blocked-term`.

Static font/layout review: `8 pass` under the current bounded contracts.

Translation status: all eight remain `ai_draft`.

Runtime status: partial. A clean 2347 route now has qSupported/`S02` readiness
and a live palette-shadow-to-hardware-DMA call (`0x03005d60` to `0x05000000`,
`0x400` bytes). There is still no natural/controlled text consumer hit,
live cache/writer-to-text-VRAM trace, changed/adjacent glyph VRAM equality,
tilemap/OAM evidence, or screen readability proof. The next work must close
those release gates or document an equivalent static writer/destination proof;
it must not add more repeated short translation batches.
