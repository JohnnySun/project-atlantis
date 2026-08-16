# A9PJ M1.6 name-entry code-unit／font-record 切片（2026-08-16）

本紀錄只保留可審核的 metadata、雜湊、位址、控制流與 bounded watchpoint receipt。
ROM、sav、完整 EWRAM／IWRAM／VRAM、圖片與原始字形 bytes 均留在 `/private/tmp`，沒有
進入 Git；本切片沒有建立日文 source table、work ledger 或翻譯 row。

## ROM 與執行期界線

| 欄位 | 值 |
| --- | --- |
| game code／title／maker | `A9PJ`／`TOW SUMMLINE`／`AF` |
| size | `8,388,608` bytes |
| SHA-256 | `b41c293fc0ed6111b7a37d960d9cd0c685e5d521a4739e0e2eaa7ff6186cfdd3` |
| GDB listener | 本 session 專用 `127.0.0.1:39123` |
| navigation gate | 初始 `DISPCNT=0x1640`；一次 `START` 後即達 keyboard signature |

工具先讀 screenblock metadata，只有 `DISPCNT=0x1B40`、`BG1CNT=0x0106` 且八個
位置全部吻合時才送 `A, RIGHT, A`。因此本次沒有重做 startup logo baseline，也沒有
把 title／scene transition 差異混入 name buffer diff。

## BG1 keyboard metadata 與 identity gate

BG1 是 4bpp、charbase `0x4000`、screenbase `0x0800`。八個位置的 entry 都是
`hflip=0`、`vflip=0`、palette bank `1`；tile ID、runtime address 與 tile hash 如下：

| slot／layout annotation | `(x,y)` | entry | tile ID | runtime tile | tile SHA-256 |
| --- | ---: | ---: | ---: | ---: | --- |
| `a-row-1`／あ | `(1,7)` | `0x1001` | `1` | `0x06004020` | `b5ae44407e13c9f6c085af00c74f47811dff6afe93020f068bdc33b8c1ff39c2` |
| `a-row-2`／い | `(2,7)` | `0x1002` | `2` | `0x06004040` | `924e28947f080def610d22c48b729b3bd86957983b679572aeb6d9da293c19f7` |
| `a-row-3`／う | `(3,7)` | `0x1003` | `3` | `0x06004060` | `742d18b92af37549e33283797b7e075eafb142426f58e19ba048a7c85c81db77` |
| `a-row-4`／え | `(4,7)` | `0x1004` | `4` | `0x06004080` | `f78b8247c640a8454bd21432ae49d56aa3aeca8e06aa03faf896f7b6de83a22d` |
| `a-row-5`／お | `(5,7)` | `0x1005` | `5` | `0x060040A0` | `4b2dd5435a020f9d11e7864f352821765e1e87b007aff7bdbba3bdc51f13a579` |
| `ka-row-1`／か | `(1,8)` | `0x101B` | `27` | `0x06004360` | `5255f765f120619881a9b57377c69d2f132a5a9ef15971ed2e3fb8df1a92e4ee` |
| `ka-row-2`／き | `(2,8)` | `0x101C` | `28` | `0x06004380` | `17ed557f340f161ec70e34d1a24cf117a395b0dd3b23511e4dd58ae852d488a5` |
| `ka-row-3`／く | `(3,8)` | `0x101D` | `29` | `0x060043A0` | `7baefffa17c0fa8fb70c8f2f2289b44e7a82e31e68289fa8b5df0cc93240e746` |

Tile ID deltas are `[+1,+1,+1,+1,+22,+1,+1]`; the runtime address stride is exactly
`0x20`. Clean-ROM search found 1/8 exact byte matches, at file offset `0x1DCC12`, but
that match is not 32-byte aligned. Aligned exact matches are `0/8`; confirmed glyph
identities are therefore `0/8`. The eight layout labels remain system-order annotations,
not a committed codepage table.

## Bounded input diff

Across input-before → first `A` → `RIGHT`/second `A`, all three screen samples retained the
same hashes and keyboard metadata:

| sample | `DISPCNT` | BG0 screenblock SHA-256 prefix | BG1 screenblock SHA-256 prefix |
| --- | ---: | --- | --- |
| before input | `0x1B40` | `e9fda91c` | `5098385e` |
| after first A | `0x1B40` | `e9fda91c` | `5098385e` |
| after second A | `0x1B40` | `e9fda91c` | `5098385e` |

The stable screen is important: the following changes are not a scene transition.

| region | before → first | first → second |
| --- | ---: | ---: |
| EWRAM changed bytes／runs | `8 / 8` | `8 / 8` |
| IWRAM changed bytes／runs | `122 / 41` | `24 / 9` |
| IWRAM append candidates | `0` | — |

Region SHA-256 receipts were `EWRAM before=8aab70bfca8a524df27cbfe67f8e56e6b8ed2c8010b79cba26e420425e1ed6eb`,
`after-first=41ab9cfa3043aef9bfcdedd5b246443dc9e05be3d9ec276133f8e1ebbdbc187`,
`after-second=0f8337b1d8c7c072aef4f5abd354ced6df865b721665a64135fe94850ebfd827`;
IWRAM receipts were `before=36ec18a99d264821cf15d33aa2a1eb9d36a940c23ef447d13abf67dbc76aacc6`,
`after-first=5c541f674e1b0e9ce7b51735d2b8bffb535ea180960720ee1c15627d4ddd580a`,
`after-second=ca56013740e7690152ecdb8870c70249a752747d18ac8a4bdac5eaa3d136cd12`.

The only bounded two-slot EWRAM candidate was `0x02004014`:

| slot | before | after first A | after second A |
| --- | ---: | ---: | ---: |
| `0x02004014` | `0x0001` | `0x005E` | `0x005E` |
| `0x02004016` | `0x0001` | `0x0001` | `0x0066` |

This is a numeric code-unit observation, not a source-text extraction. The private phase
receipts also retain full-region hashes and raw snapshots for rerun comparison.

## Writer／reader receipt

The writer rerun used a 2-byte write watchpoint at `0x02004014`; the reader rerun used a
2-byte read watchpoint at the same address. Both were one-shot and were removed before
diagnostic memory reads so the read watchpoint could not self-trigger.

### Writer for the first known slot

Receipt: `T05watch:02004014;`, during the first `A`, with `code_unit=0x005E`.

| register | value |
| --- | ---: |
| PC | `0x08052BBC` |
| LR | `0x0806B66F` |
| `r0` | `0x0000005E` |
| `r3` | `0x02004008` |
| `r5` | `0x0808884C` |
| `r6` | `0x02004000` |
| SP | `0x03007EAC` |

The static Thumb instructions at `0x08052BB8`/`0x08052BBA` are `ldrh` followed by
`strh ..., [r3,#0xC]`; `0x02004008 + 0xC = 0x02004014`. This ties the first input to a
16-bit buffer write, rather than merely to an EWRAM diff.

### Reader during display refresh

Receipt: `T05rwatch:02004014;`, during the bounded second-input display path. The loaded
value is `0x005E`:

| register | value |
| --- | ---: |
| PC | `0x080063B8` |
| LR | `0x080063C7` |
| `r2` | `0x060022E0` |
| `r3` | `0x0000005E` |
| `r5` | `0x02004014` |
| `r6` | `0x00000030` |
| SP | `0x03007E7C` |

The preceding Thumb instruction at `0x080063B6` is `ldrh r3,[r5]`; the caller then reaches
`bl 0x080049A0`. This is a confirmed code-unit consumer/caller. The bounded receipt did
not claim that `r2` is the final VRAM tile address; that downstream address remains a
separate question.

## Font-record arithmetic and causal boundary

At `0x080049A0`, the renderer masks the loaded 16-bit unit and at `0x080049C8` computes
`code_unit * 0x18`. The literal at `0x08004B00` is the ROM bus base `0x08089E00`. The
observed units therefore address these 24-byte ROM font records:

| known slot | code unit | record formula | file offset | record SHA-256 |
| --- | ---: | ---: | ---: | --- |
| `a-row-1`／あ | `0x005E` | `0x08089E00 + 0x005E*0x18` | `0x8A6D0` | `aeac7e6ca436cfd8533f3171e8ddb3e790601dde94b1f7bedc5cfff3b9cad741` |
| `a-row-2`／い | `0x0066` | `0x08089E00 + 0x0066*0x18` | `0x8A790` | `207f45437ff6d4c5fae7598547f0b89c6670991689cd64f44ea26f87b320b964` |

The resulting chain is now:

```text
known keyboard slot
  -> KEYINPUT A / RIGHT / A
  -> EWRAM 16-bit code unit (0x005E, then 0x0066)
  -> writer PC 0x08052BBC
  -> reader ldrh at 0x080063B6 / caller PC 0x080063B8
  -> renderer 0x080049A0
  -> ROM font-record table 0x08089E00 + unit * 0x18
```

The selected BG1 runtime tile addresses and the font-record path are deliberately kept as
separate evidence dimensions. This bounded input run did not install a charblock/DMA
watchpoint, and it captured no direct font-tile write; the BG1 screenblock stayed unchanged.
The DMA/copy boundary therefore remains open. This milestone confirms a code-unit consumer
and font-record arithmetic, but not the final runtime-tile identity, controls, or a general
script decoder.

## Tooling and repeatability

Game-specific additions:

- `tools/m16_keyboard_metadata.py`: tilemap fields, tile address/hash and bounded ROM match.
- `tools/m16_name_entry_probe.py`: adaptive keyboard gate, EWRAM/IWRAM diff/filter,
  one-shot writer/reader receipt and font-record address math.
- `tools/test_m16_keyboard_metadata.py`: five pure tests for tilemap, hash, diff/filter and
  address arithmetic.

Private runtime output used for this record:

```text
/private/tmp/tow-a9pj-m16-phase2/
/private/tmp/tow-a9pj-m16-phase3/
```

No path above is a repository input or a commit path. The tool only emits source-like rows
after a later identity gate; this M1.6 result leaves source extraction and translation closed.

Verification completed for this slice:

```text
core/gba tests: 6 passed
game-specific tests: 5 passed
ROM identity: A9PJ / TOW SUMMLINE / SHA-256 b41c293f...cfdd3
repository safety: passed (504 visible files)
git diff --check: passed
```
