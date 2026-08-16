# B3CJ semantic multi-resource container rebuild

This is a release-gate engineering receipt, not a translation batch. It keeps
all eight existing ledgers at `zh-TW`/`ai_draft` and writes the rebuilt ROM,
summary, and BPS only to ignored `work/` paths.

## Fixed inputs and command

- clean B3CJ ROM SHA-256: `39bc4cf448106aa4b8cdde235632ffb57432c4b1919c8843510b70b3787fad2d`
- clean B3CJ CRC32: `12afae5d`
- header checksum: `0x6b`, unchanged by the rebuild
- fixed reviewed resource IDs: `9,10,11,12,14,15,16,17,18,19,22,24,25`
- fixed csm3 revision remains `7e388ac861bbac289b1f86dc5b8fa46d47b1a1a2`

Re-run:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 \
  games/summon-night-craft-sword-3/tools/rebuild_container.py \
  games/summon-night-craft-sword-3/roms/base/B3CJ-jp-from-zip.gba \
  --output games/summon-night-craft-sword-3/work/m5-container-rebuilt.gba \
  --summary-output games/summon-night-craft-sword-3/work/m5-container-rebuild-summary.json \
  --bps-output games/summon-night-craft-sword-3/work/m5-container-rebuilt.bps \
  --bps-applied-output games/summon-night-craft-sword-3/work/m5-container-rebuilt-applied.gba
```

## Static evidence

`rebuild_container.py` re-emits every parsed PSI3 token, including opaque
spans, then deterministically recompresses each unique non-zero payload with
the existing bounded GBA LZ77 encoder. It preserves the type-2 directory and
writes each result only within its existing pointer span, zero-filling the
unused tail.

| receipt | value |
| --- | --- |
| resources / unique payload groups | `13 / 11` |
| records before / after | `361 / 361` |
| decoded stream bytes | `32092` |
| source Shift-JIS re-encode | `361/361` |
| opaque tokens / rejected marker candidates | `203 / 1` |
| PSI3 stream round-trip aggregate | `154704fa319346491005c471b8ccb6ef4740463935b77eb541791736122d1937` |
| stable record identity digest | `fc8ac5a8754d0e804b2bbfe06d7a73ccbcb530c1b75eccc821359030fc7bcfca` |
| changed bytes | `8191`, all inside reviewed payload spans |
| directory bytes | byte-identical |
| rebuilt ROM SHA-256 / CRC32 | `badb5838efafc3eb585c271208281bf44ce120ab46ec1ad573b4ddd55d185793` / `5344e805` |
| BPS size / SHA-256 | `8615` / `326217ae194287d394fda8ef0296e095dff378d0c034238a48cae9c848080034` |
| BPS apply | byte-identical; applied SHA matches rebuilt ROM |

Every group passed its capacity guard. The recompressed bytes are not expected
to match the original compressor output; the independently decoded PSI3
streams, source-record identities, pointer directory, and bounded spans do.

## Boundary

This closes the semantic multi-resource LZ77/container no-op layer for the 13
reviewed IDs. It does not prove unknown VM semantics, variable-length
translated records in every resource, a general pointer-relocation policy, a
live renderer, tilemap placement, screen readability, or a publishable patch.
The existing resource-24 translation batches remain the only translated
container rebuilds.
