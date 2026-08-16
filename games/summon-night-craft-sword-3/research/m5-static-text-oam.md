# B3CJ static text-object to OAM evidence

This is a release-gate supplement, not a new translation batch. It extends the
existing static writer/DMA audit with the local text-object and OAM serializer
callsites. It does not claim runtime reachability or screen readability.

## Fixed inputs and guards

- ROM identity: the clean ignored B3CJ dump; the tool first reruns
  `audit_static_render_destination.py` and therefore retains its strict ROM,
  13-function, 16-literal writer/DMA/palette/OAM guards.
- csm3 review revision: `7e388ac861bbac289b1f86dc5b8fa46d47b1a1a2`.
- Additional local function guards:
  - `sub_0800B730` text-object setup, file range `0xb730..0xb8f4`, SHA-256
    `59feabb18a62ea301bb7d453dca387fda15076a9f4a8a5b8758a56e73b37df38`.
  - `sub_0800901C` main-loop OAM packer, file range `0x901c..0x9108`, SHA-256
    `e6d1f338dfb6acf124f197e77f14460a5563480d301900e973522c00b98272b1`.
- Additional local literal guards at `0x90f4..0x9104` resolve to
  `0x030038b0`, `0x030037a0`, `0x03003cc0`, `0x03003cb0`, and `0x030037b0`.

## Static chain

The reviewed csm3 callsites and matching B3CJ bytes establish this bounded
chain:

```text
sub_0800D81C
  -> sub_0800B730
       -> sub_080036F8 -> sub_08002CB4 (glyph output)
       -> per-glyph object descriptor, stride 0x28
sub_08001C00
  -> sub_0800901C
       -> gUnk_03003CC0 / gUnk_030037B0 -> gOamBuffer (0x030038b0)
sub_08001BC0
  -> sub_080092CC -> 0x07000000 (0x400-byte OAM DMA)
```

Within the bounded `sub_0800B730` body, the local assembly loops over the
decoded glyph count, initializes and fills the object descriptors through
`sub_08009F0C`, `sub_08009F50`, `sub_0800A630`, `sub_0800A6C0`, and
`sub_0800A6CC`, then advances the descriptor by `0x28` bytes. The main-loop
`sub_0800901C` consumes the linked object state and writes three OAM attribute
halfwords per object into `gOamBuffer`; the existing local `sub_080092CC`
audit independently proves the later hardware destination and DMA control.

This is stronger than a standalone `0x030038b0` literal: the text-window
consumer, per-glyph loop, main-loop serializer, and OAM transfer are all
separately hash-guarded. It is still static evidence only. It does not prove
that the eight patched records were naturally reached, that slots
`0x847/0x848/0x849` were present in a live object, or that any OAM entry was
visible on screen.

## Reproduction and boundary

```sh
PYTHONDONTWRITEBYTECODE=1 python3 \
  games/summon-night-craft-sword-3/tools/audit_static_text_oam.py \
  games/summon-night-craft-sword-3/roms/base/B3CJ-jp-from-zip.gba \
  --output games/summon-night-craft-sword-3/work/m5-static-text-oam.json
```

The ignored report must print `B3CJ_STATIC_TEXT_OAM_AUDIT_OK functions=2
literals=5 buffer=gOamBuffer at 0x030038b0`. Its fail-closed tests reject
function or literal drift. Tilemap destination, live OAM values, live VRAM,
palette readback, natural reachability, and screen readability remain unknown;
the eight tracked ledgers remain `zh-TW` / `ai_draft`.
