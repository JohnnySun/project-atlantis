# M3 bounded batch 2：Table B coverage extension 與固定槽位 round-trip

日期：2026-08-16（Asia/Taipei）

本切片延伸已建立的 Table B fixed-slot boundary，處理 19 個可由現有 codepage 覆蓋的
unique battle-effect records。B0–B5 的 batch 1 另有獨立 receipt；本檔不把 aliases 或
controlled runtime 當成新增自然 reachability。完整日文原文、ROM、work、patched ROM、
BPS 和 extractor 輸出均留在 ignored／`/private/tmp`。

## confirmed

- `translations/table-b-batch-2.jsonl` 有 19 筆 source-free ledger rows：
  `018`、`022`、`023`、`024`–`037`、`041`、`042`。每筆保留 B3EJ revision、string ID、
  source hash、`zh-TW` target、上下文、max width、控制碼清單與 `ai_review` 狀態；
  tracked ledger 沒有 `source` 欄位。
- ignored source table 經 `restore_translations.rb` 產生本機 work copy；
  `strip_translations.rb` 後的輸出與 tracked ledger 逐 byte 相同，record count `19`，
  source fields `0`。這只證明 ledger／來源隔離流程，不代表語意已完成最終人工審核。
- `font_coverage.py` 對 19 筆目標取得 `covered_count=19`、`fit_count=19`、missing
  codepage entry `0`；strict Shift-JIS、1834-entry codepage、兩組 glyph bank 的
  0x20-byte slot 與原固定槽位長度均通過。
- `patch_table_b.py` 只接受 Table B string ID、現行 source hash／source-text hash、
  strict coverage 和 fixed span；relocation 關閉。19 筆為 19 個 unique targets，
  changed bytes `238`，44-entry pointer table 保持不變。
- `verify_table_b_patch.py` 取得 `entry_count=44`、`selected_entry_count=19`、
  `selected_reextract_match_count=19`、`selected_fixed_slot_count=19`、
  `changed_byte_count=238`。未選取 records byte-identical，selected records 的
  bounded decode→re-encode／NUL span 均相符。
- batch 2 BPS 使用共用 `core/patches/bps_create.rb`／`bps_apply.rb`：patch size `329`
  bytes，source CRC32 `a4a1c956`、target CRC32 `0e327fc6`、patch CRC32 `9cb20352`；
  BPS SHA-256 為 `a62f629e6019198761cfb01c0dcb5a241c07f7f69282261db077875f30fb963a`。
  clean ROM 套用 BPS 後與 encoder 產生的 patched ROM `cmp` 相等；patched SHA-256 為
  `6cbbaa3b291cd02adcac442c30ded5661a84d0bd5d7265e10160175ea047987a`。

## provisional

- batch 2 仍是 Table B battle-effect label；`攻勢加強`、`防護加強`、`失序`、`吸取` 等
  wording 是在既有 codepage gate 下的 zh-TW 候選，需依自然畫面與公開術語基線再審核，
  不當作已鎖定的全遊戲用語。
- Table B 的 aliases 未重複建立 ledger rows：batch 1／2 以 unique record target 綁定，
  patch verifier 另檢查 44 entries 的 pointer table 與未選取 record。這個去重策略只
  適用已證實的 Table B pointer alias，不能套到未解析的 pool A/C/D。
- 兩批合計覆蓋 Table B `25/26` unique records；`b3ej:table-b:020` 因繁體 `經驗` 的
  codepage units `0xE353`／`0xE984` 尚無現有 glyph，保留在 pending，而不是使用未核准
  的日文 variant。

## negative／pending

- batch 2 沒有自然 runtime cohort。M2.4 的 natural paths 仍停在 title/input-read
  loop；patched batch 1 的 single-connection receipt 是 controlled consumer only，
  不證明 batch 2 自然選單／戰役畫面 reachability。
- 尚未以 batch 2 patched ROM 完成自然 menu／battle／story scene QA；未測 pool A/C/D、
  Table B withheld entry、劇情、武將、地名、官職、策略與完整版面。
- 全遊戲 encoder 仍未成立：目前只保證 Table B selected fixed spans、無 relocation、
  no-control target 與 existing font coverage。繁體缺字、全形排版、換行／控制碼、自然
  event index `<44`、全池重抽取仍是 roadmap 缺口。

## 可重現命令（輸出留在 ignored／暫存）

```text
ruby core/ledger/restore_translations.rb \
  games/sangokushi-eiketsuden/translations/table-b-batch-2.jsonl \
  /private/tmp/b3ej-all-source-v3.jsonl /private/tmp/b3ej-batch2-work.jsonl
ruby core/ledger/strip_translations.rb \
  /private/tmp/b3ej-batch2-work.jsonl /private/tmp/b3ej-batch2-stripped.jsonl
cmp games/sangokushi-eiketsuden/translations/table-b-batch-2.jsonl \
  /private/tmp/b3ej-batch2-stripped.jsonl
PYTHONDONTWRITEBYTECODE=1 python3 games/sangokushi-eiketsuden/tools/font_coverage.py \
  games/sangokushi-eiketsuden/roms/base/B3EJ_JP_candidate.gba \
  --work /private/tmp/b3ej-batch2-work.jsonl --output /private/tmp/b3ej-batch2-font.json
PYTHONDONTWRITEBYTECODE=1 python3 games/sangokushi-eiketsuden/tools/patch_table_b.py \
  games/sangokushi-eiketsuden/roms/base/B3EJ_JP_candidate.gba \
  --work /private/tmp/b3ej-batch2-work.jsonl \
  --output /private/tmp/b3ej-batch2-patched.gba \
  --metadata-output /private/tmp/b3ej-batch2-patch.json
PYTHONDONTWRITEBYTECODE=1 python3 games/sangokushi-eiketsuden/tools/verify_table_b_patch.py \
  games/sangokushi-eiketsuden/roms/base/B3EJ_JP_candidate.gba \
  /private/tmp/b3ej-batch2-patched.gba \
  --work /private/tmp/b3ej-batch2-work.jsonl \
  --output /private/tmp/b3ej-batch2-verify.json
ruby core/patches/bps_create.rb \
  games/sangokushi-eiketsuden/roms/base/B3EJ_JP_candidate.gba \
  /private/tmp/b3ej-batch2-patched.gba /private/tmp/b3ej-table-b-batch2.bps
ruby core/patches/bps_apply.rb \
  games/sangokushi-eiketsuden/roms/base/B3EJ_JP_candidate.gba \
  /private/tmp/b3ej-table-b-batch2.bps /private/tmp/b3ej-batch2-applied.gba
cmp /private/tmp/b3ej-batch2-patched.gba /private/tmp/b3ej-batch2-applied.gba
```

下一個安全邊界是先處理 withheld entry 的繁體字庫／Unicode identity 設計，再擴充到
pool A/C/D；在此之前不能把 Table B 的 25/26 覆蓋率外推為完整文本翻譯或回插完成。
