# M3 story-event E batch 2 round-trip（2026-08-16）

本批次只處理 story-event E:032 的獨立四行結局敘事。source 仍只在 ignored
ROM-derived source table／work；本文件只保存 hash、計數、控制碼和 BPS metadata。

| 欄位 | 結果 |
|---|---:|
| selected entry | E:032 |
| record file offset | `0x077E68` |
| original payload span | 85 bytes |
| strict codepage coverage / fit | 1/1 / 1/1 |
| LF/control invariant | 1/1；3 LF，無其它控制碼 |
| current four-pool custom-unit overlap | 0；17-unit guard enabled |
| fixed-slot changed bytes | 81 |
| pointer table | unchanged |
| relocation | disabled |

`tools/patch_fixed_pool.py --pool story-event --custom-map ...` 只接受 standard
Shift-JIS/codepage target，並保留原始 control-byte sequence。四行 target 保留 E:032
的 3 個 LF；ASCII comma/period 避開 E source 與既有 custom map 重疊的 raw units。
這是 existing-codepage gate，不是 custom glyph safety 或自然畫面證據。

Round-trip receipt：

- `verify_fixed_pool_patch.py` selected re-extract／fixed-slot `1/1`；未選取 records
  byte-identical；E pointer table unchanged；
- source CRC32 `a4a1c956`；patched target CRC32 `8b229520`；
- patched ROM SHA-256 `77ad02e63074b8ca93c31da250dcdfea09de96c222d27536b1962cbf440ecb21`；
- BPS 117 bytes，BPS CRC32 `785079cd`，BPS SHA-256
  `602ff6cfc2e3bb4fe9c36b8a5502470fcbce97ac76bef3c37ffd99502ed314ea`；
- clean ROM + BPS apply 與 patched ROM `cmp` 相同。

## Runtime boundary

本批次後仍未取得 E 的自然 formatter→glyph cache→VRAM／tilemap receipt。一次自己
啟動的 headless mGBA 嘗試可執行 patched ROM，但 GDB stub 回報固定 2345 socket
無法開啟；Qt binary 也無可用 offscreen platform。process 已停止，沒有連線或終止
其他 session。這是 transport negative，不能解讀成遊戲自然不可達；E runtime QA
仍 pending。
