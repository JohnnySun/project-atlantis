# M3 bounded batch：event-system pool fixed-slot round-trip

日期：2026-08-16（Asia/Taipei）

本切片處理已由 bounded decoder 固定的 event-system pool D，僅選擇可由現有
codepage 覆蓋、且不超過原始固定槽位的短 menu／event labels。完整日文原文、ROM、
work、patched ROM、BPS 和 extractor 輸出均留在 ignored／`/private/tmp`；本檔只保存
可重跑的計數、hash、邊界與限制。

## confirmed

- `translations/event-system-batch-1.jsonl` 有 9 個 source-free ledger rows：
  `001`、`002`、`009`、`012`、`016`、`017`、`018`、`019`、`023`。每筆保留 B3EJ
  revision、string ID、source hash、`zh-TW` target、上下文、max width、控制碼清單和
  `ai_review` 狀態；tracked ledger 沒有 `source` 欄位。
- pool D 的 reviewed boundary 是 file base `0x0D4D00`、28 entries、16 unique
  record targets。ignored source table 的 bounded extractor 對 28/28 entries 通過
  pointer／NUL／Shift-JIS 結構檢查；D pool 內的 payload 長度分布為 0-byte `6`、
  4-byte `15`、6-byte `2`、10-byte `3`、12-byte `2`。本批次只覆蓋其中 9 個 unique
  targets，沒有把 aliases 重複寫成翻譯 rows。
- ignored source table 經 `restore_translations.rb` 產生本機 work copy；
  `strip_translations.rb` 後的輸出與 tracked ledger 逐 byte 相同，record count `9`、
  source fields `0`。這只證明 ledger／來源隔離流程，不代表語意已完成最終人工審核。
- `font_coverage.py` 對 9 筆目標取得 `covered_count=9`、`fit_count=9`、missing
  codepage entry `0`；strict Shift-JIS、1834-entry codepage、兩組 glyph bank 的
  0x20-byte slot 與原固定槽位長度均通過。
- `patch_fixed_pool.py` 只接受明確的 `event-system` pool、現行 source hash／
  source-text hash、strict coverage 和 fixed span；relocation 關閉。9 筆為 9 個
  unique targets，changed bytes `34`，ROM size 保持 `4194304` bytes，28-entry
  pointer table 保持不變。
- `verify_fixed_pool_patch.py` 取得 `entry_count=28`、`selected_entry_count=9`、
  `selected_reextract_match_count=9`、`selected_fixed_slot_count=9`、
  `changed_byte_count=34`；未選取 records byte-identical，selected records 的
  bounded decode→re-encode／NUL span 均相符。
- event-system batch 1 BPS 使用共用 `core/patches/bps_create.rb`／`bps_apply.rb`：
  patch size `78` bytes，source CRC32 `a4a1c956`、target CRC32 `510f7391`、
  patch CRC32 `0c4e4642`；BPS SHA-256 為
  `c390363916b70f034741f4e83042a35887dfb164dbf82205101aa6a097141551`。
  clean ROM 套用 BPS 後與 encoder 產生的 patched ROM `cmp` 相等；patched SHA-256 為
  `9ee608623a6476695710e833e9185b9cfde43f6c5c930413c1d6069b06efd4e7`。

## provisional

- 9 筆是 event-system menu／ending label 的 bounded zh-TW 候選；目前狀態仍為
  `ai_review`，需要自然 menu／event 畫面核對臺灣 UI 用語與實際上下文。這個批次不把
  static pool 分類直接當成自然 reachability。
- D pool 尚有 7 個 unique targets 未建立翻譯 ledger；其中空字串 entries 保留在
  decoder 統計中，不因空字串猜測畫面語意。pool A/C、劇情／戰役與其他系統 pool
  仍未翻譯。
- 先前一次測試版 helper 把固定 span 少算一個 byte，產生 3-byte ROM shrink；該輸出
  在本機驗證前即丟棄，沒有進入 BPS、runtime、tracked file 或任何 hash receipt。修正
  後的 verifier 明確要求 ROM size 不變並重新取得本檔的數值。

## negative／pending

- 本切片沒有自然 runtime cohort，也沒有把 Table B controlled receipt 擴大成
  event-system 的自然畫面證據。尚未在 mGBA 取得 D menu／ending 的自然 formatter→
  glyph cache→VRAM/tilemap receipt。
- 尚未完成 D pool 其餘 7 個 unique records、pool A/C、完整劇情／戰役、武將／地名／
  官職／策略／道具術語批次、缺字 `經／驗` 的合法字型來源與 Unicode mapping。
- 目前只證明 pool D selected record layer 的 fixed-slot encoder、re-extract 和 BPS
  apply；不宣稱全遊戲 encoder、全池 round-trip、全形排版、控制碼、自然 event index
  `<44` 或發行 ROM 已完成。

## 可重現命令（輸出留在 ignored／暫存）

```text
ruby core/ledger/restore_translations.rb \
  games/sangokushi-eiketsuden/translations/event-system-batch-1.jsonl \
  /private/tmp/b3ej-all-source-v3.jsonl /private/tmp/b3ej-event1-work.jsonl
ruby core/ledger/strip_translations.rb \
  /private/tmp/b3ej-event1-work.jsonl /private/tmp/b3ej-event1-stripped.jsonl
cmp games/sangokushi-eiketsuden/translations/event-system-batch-1.jsonl \
  /private/tmp/b3ej-event1-stripped.jsonl
PYTHONDONTWRITEBYTECODE=1 python3 games/sangokushi-eiketsuden/tools/patch_fixed_pool.py \
  games/sangokushi-eiketsuden/roms/base/B3EJ_JP_candidate.gba \
  --pool event-system --work /private/tmp/b3ej-event1-work.jsonl \
  --output /private/tmp/b3ej-event1-patched.gba \
  --metadata-output /private/tmp/b3ej-event1-patch.json
PYTHONDONTWRITEBYTECODE=1 python3 games/sangokushi-eiketsuden/tools/verify_fixed_pool_patch.py \
  games/sangokushi-eiketsuden/roms/base/B3EJ_JP_candidate.gba \
  /private/tmp/b3ej-event1-patched.gba --pool event-system \
  --work /private/tmp/b3ej-event1-work.jsonl \
  --output /private/tmp/b3ej-event1-verify.json
ruby core/patches/bps_create.rb \
  games/sangokushi-eiketsuden/roms/base/B3EJ_JP_candidate.gba \
  /private/tmp/b3ej-event1-patched.gba /private/tmp/b3ej-event-system-batch1.bps
ruby core/patches/bps_apply.rb \
  games/sangokushi-eiketsuden/roms/base/B3EJ_JP_candidate.gba \
  /private/tmp/b3ej-event-system-batch1.bps /private/tmp/b3ej-event1-applied.gba
cmp /private/tmp/b3ej-event1-patched.gba /private/tmp/b3ej-event1-applied.gba
```
