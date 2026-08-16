# M2 framework-native B3TJ runtime case（2026-08-16）

## Case contract

[`b3tj-clean-state4-runtime-case.json`](b3tj-clean-state4-runtime-case.json) is the
first B3TJ manifest for the shared `gba-runtime-validation` runner. It contains no
ROM path, source text, raw bytes, screenshot, save state, or guessed glyph metrics.
The pinned clean ROM identity is SHA-256
`d083d66b818b1353a449af7f1dd4232b490c254a4107951a3749973d03a0a394`, size
`16777216`, and game code `4233544a` (`B3TJ`).

The static section records only the selected strict boundary `0x146EE0–0x146EE4`
and a five-byte adjacent guard. It deliberately omits layout/glyph widths and uses
no codepage claim; the selected record is an observed boundary, not a translation
target contract yet. The runtime section declares a natural clean-boot/state4 case:
dispatcher entry, state4 input loop, active-low START/A through the observed KEYINPUT
destination `r1`, bounded state captures, and BG0/OAM render hashes.

## Static evidence

| check | result |
| --- | --- |
| `validate-manifest` | pass |
| clean-ROM identity/size/game code | pass |
| selected record terminator | pass; unit index `4` within allocated length `5` |
| adjacent/target region receipts | pass; hashes only |
| report safety checker | `valid fail-closed report: pass` |

The static report is an ignored `/private/tmp` artifact. It contains only SHA-256,
offset, length, terminator, and count metadata. It does not prove a live consumer,
glyph identity, text rendering, or reinserted-ROM behavior.

## Runtime status

The manifest runtime actions have not yet been exercised by the framework runner. A
fresh B3TJ mGBA process could not be launched in the current turn because the local
debugger-socket escalation approval service repeatedly returned
`stream disconnected`; the sandbox fallback returned `Debugger: Couldn't open socket`.
No process was left running and this setup condition is not classified as a ROM or
consumer failure. Existing game-specific M1.8/A82AC receipts remain separately
classified and are not silently upgraded to a framework-native `pass`.

The resumed bounded retry kept the ownership boundary explicit. Port `2345` was
already owned by another session's mGBA (PID `37309`) and `2347` by another
session's mGBA (PID `3494`); neither process was contacted or stopped. Fresh bind
probes found `39123` and `2348` free. A pre-existing headless mGBA build intended
for the independent lane was started with B3TJ and `-g`, but its own
`Debugger: Couldn't open socket` result was the same sandbox socket restriction;
the process was stopped immediately. An escalated launch of the pre-existing
2348 build was rejected by the approval service before process creation. The
headless binary also rejects `-d`, so the CLI-debugger fallback is unavailable.
These are environment/setup negatives only: there is no new B3TJ runtime hit or
game-level negative in this receipt.

When the listener capability is restored, run the exact case with a newly owned
process and then inspect `required`, `exercised`, and `unproven` capabilities. Any
missing breakpoint, watchpoint, render, or input evidence must remain `unknown`.
The case is not the final localization QA: a later patched-ROM case must additionally
assert target/adjacent preservation, decoder/control/glyph/layout behavior, and
re-extraction/BPS/runtime consistency.

The next narrow consumer contract is
[`b3tj-state7-selected-record-runtime-case.json`](b3tj-state7-selected-record-runtime-case.json).
It sequences the already confirmed normal state-4 input path, a state-7 entry stop,
the fixed parser callsite `0x08001D92`, parser entry `0x080025CC`, and a read watch on
the selected strict boundary `0x08146EE0`. This contract has not been exercised; until
it produces the callsite and parser stops followed by a classified source read, the
consumer, decoder, glyph, and VRAM fields remain unknown.

## Reproducible commands

```sh
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 \
  scripts/gba-runtime-qa.py validate-manifest \
  games/tales-of-the-world-narikiri-dungeon-3/research/b3tj-clean-state4-runtime-case.json

PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 \
  scripts/gba-runtime-qa.py static \
  games/tales-of-the-world-narikiri-dungeon-3/research/b3tj-clean-state4-runtime-case.json \
  --base-rom games/tales-of-the-world-narikiri-dungeon-3/roms/base/Tales_of_the_World_Narikiri_Dungeon_3_JP_AGB-B3TJ-JPN.gba \
  --output /private/tmp/tow-nd3-runtime-case-static.json

PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 \
  .agents/skills/gba-runtime-validation/scripts/check_report.py \
  /private/tmp/tow-nd3-runtime-case-static.json

# Start a fresh, owned B3TJ mGBA first, verify its listener/PID, then:
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 \
  scripts/gba-runtime-qa.py runtime \
  games/tales-of-the-world-narikiri-dungeon-3/research/b3tj-clean-state4-runtime-case.json \
  --rom games/tales-of-the-world-narikiri-dungeon-3/roms/base/Tales_of_the_World_Narikiri_Dungeon_3_JP_AGB-B3TJ-JPN.gba \
  --port <owned-b3tj-gdb-port> \
  --output /private/tmp/tow-nd3-runtime-case-runtime.json
```
