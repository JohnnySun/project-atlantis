# B3CJ M1.5/M2.1 靜態格式證據

本文件描述已由固定 B3CJ ROM 與 csm3 callsite 交叉驗證的最小格式，不保存日文原文。完整抽取結果只在 ignored 的 `research/summon-night-craft-sword-3-decoded.jsonl`。

## 已確認的資源鏈

| 層次 | 已確認內容 | 證據 |
| --- | --- | --- |
| resource directory | type 2 table `gUnk_09718FFC`，ROM file offset `0x1718ffc`，大小 `0x284`，可解析 resource ID `0..78` | csm3 `src/main.c:480-505` 的 `gUnk_03002970` 初始化與 `sub_08001D3C`；本機 table 的 little-endian entries 可全部落在 ROM 內 |
| pointer arithmetic | `directory = table + 4 * (2 * id + 2)`；`payload = table + relative_units * 16` | csm3 pointer type 是 `int *`，`sub_08001D3C` 的 `*var * 4` 以 4-byte int 對齊；本機 resource 9、12、14、24 等 payload 均可重現 |
| compression | payload 是標準 GBA LZ77：header `0x10`、24-bit little-endian expanded size、flag bits MSB-first | csm3 `sub_08012D30` 明確呼叫 `LZ77UnCompWram`；bounded decoder 對本機 type-2 payload 成功解壓 |
| script container | 解壓結果以 `PSI3` 開頭；script stream 從解壓 offset `0x10` 開始 | csm3 `sub_08012E14` 將 buffer `+0x10` 設成 halfword consumer base；本機所有被抽取資源均通過 `PSI3` gate |
| text record | `0x0308` little-endian VM marker，後接記憶體原始 byte order 的日文 bytes，至 `0x0000` 結束 | 本機 13 個含 record 的 resource ID 共抽出 361 筆；每筆 strict Shift-JIS decode 成功，control token 統一為 `0x0308`／`0x0000` |

注意：VM 以 little-endian halfword 讀 marker 與控制資料，但 marker 後的 codepage bytes 不先逐 halfword swap；Data Crystal TBL 的 16-bit code 值在 ROM 中按 raw memory byte order 解讀。這個判定由多個實際記錄的 strict decode、長度與 hash 重抽結果支持，而不是只因 TBL 存在就假定。

## 可重抽取的真實群組

以下只列 provenance 與 raw hash 前綴，不列出原文：

| string_id 群組 | 解壓 offset 例 | raw length 例 | raw SHA-256 前綴 | pointer／consumer／codepage 證據 |
| --- | ---: | ---: | --- | --- |
| `b3cj:t2:009:*` | `0x03b6` | 36 | `dce5f7e1ceb36900` | type-2 pointer + csm3 LZ77/stream consumer + strict Shift-JIS |
| `b3cj:t2:012:*` | `0x00a6` | 22 | `eb8c824818ac004b` | type-2 pointer + csm3 consumer + strict Shift-JIS |
| `b3cj:t2:014:*` | `0x0084` | 34 | `f0cd7c1b793a50c7` | type-2 pointer + csm3 consumer + strict Shift-JIS |
| `b3cj:t2:018:*` | `0x0052` | 30 | `6f5372dc723e5325` | type-2 pointer + csm3 consumer + strict Shift-JIS |

抽取收據：361 筆、resource IDs `9,10,11,12,14,15,16,17,18,19,22,24,25`；M2.1 ignored JSONL 的 SHA-256 為 `a050790267679a35b1300f8ed3056271b6c481124790e9249484ce9d1d7966e3`。輸出欄位包含 stable `string_id`、resource directory offset、relative pointer units、payload offset/CPU address、compressed/decompressed size/hash、script magic、structured control data 與 consumer evidence。控制碼與 stream round-trip 的完整收據見 [`research/m2.1-control-roundtrip.md`](m2.1-control-roundtrip.md)。

## 重跑方式

```sh
PYTHONDONTWRITEBYTECODE=1 python3 games/summon-night-craft-sword-3/tools/extract_static.py \
  games/summon-night-craft-sword-3/roms/base/B3CJ-jp-from-zip.gba \
  --output games/summon-night-craft-sword-3/research/summon-night-craft-sword-3-decoded.jsonl
```

工具固定要求 B3CJ、32 MiB、CRC32 `12afae5d`、SHA-1 `3f5253fcf57e07ce52472bd29a61d16b98a12376` 與 header checksum `0x6b`，並限制 table、expanded size 與 record 數量。JSONL 是 ignored source boundary，不能 stage。

## 尚未證實的部分

- `0x0302`、`0x0304`、`0x0316`、`0x047e` 等周邊 VM word 的 handler、參數寬度與語意仍保留 opaque；`0x0309`／`0x030A` 只有 callsite-level input/state 形狀。
- 字型 tile 位址、glyph lookup、glyph identity 與 VRAM 對應尚未證實。
- 字串修改後的長度契約、指標重建、編碼器與可逆回插路徑尚未建立。

因此 M2.1 只宣稱「已命名控制形狀的 record/stream parser 與 no-op round-trip 已成立」，不宣稱完整 script VM、字型、翻譯或 ROM 回插已完成。
