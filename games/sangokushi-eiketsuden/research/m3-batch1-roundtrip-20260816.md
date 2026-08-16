# M3 bounded batch 1：Table B B0–B5 與固定槽位 round-trip

日期：2026-08-16（Asia/Taipei）

本切片只處理已固定邊界的 Table B 六筆短 label：`b3ej:table-b:000` 至
`b3ej:table-b:005`。完整日文原文、ROM、工作帳本、patched ROM、BPS 和 extractor
輸出均留在 ignored／`/private/tmp`；本檔只保留可重跑的計數、位址、hash 和限制。

## confirmed

- `translations/table-b-batch-1.jsonl` 有 6 筆 source-free ledger rows；每筆保留
  B3EJ revision、string ID、source hash、`zh-TW` target、上下文、max width、控制碼清單
  與 `ai_review` 狀態。tracked ledger 不含 `source` 欄位。
- 本機 `restore_translations.rb` 以 ignored decoded source table 產生 work copy；
  `strip_translations.rb` 後的輸出與 tracked ledger 逐 byte 相同，record count `6`，
  source fields `0`。這只證明 ledger schema／來源隔離流程，不代表翻譯已通過人工或
  runtime 審核。
- `font_coverage.py` 對 6 筆目標的 strict Shift-JIS 編碼、1834-entry codepage、兩組
  glyph bank 的 0x20-byte slot 都通過：`covered_count=6`、`fit_count=6`、missing
  codepage entry `0`。ASCII／單位元組處理和 double-byte code unit 分開計算；沒有把
  Unicode identity 從 glyph hash 反推。
- `patch_table_b.py` 只接受 `b3ej:table-b:NNN`、現行 source hash／source-text hash、
  strict codepage coverage 和原 record fixed span；relocation 明確關閉。B0–B5 指向
  `6` 個 unique target，改變 `42` bytes；Table B 的 `44` 個 pointer bytes 未改變。
- `verify_table_b_patch.py` 在 clean／patched ROM 上取得：`entry_count=44`、
  `selected_entry_count=6`、`selected_reextract_match_count=6`、
  `selected_fixed_slot_count=6`、`changed_byte_count=42`。未選取的 records byte-identical，
  selected records 的 bounded decode→re-encode／NUL span 皆相符；這是 record/table
  層 receipt，不是全 ROM insertion proof。
- patched ROM 的一次 controlled runtime receipt 已完成：本 session 自有 mGBA process、
  PID `83841`、native GDB port `2346` readiness 均通過，使用單一 connection；harness
  以 `--allow-fixed-slot-variant` 明確核對 B0 payload 仍在 clean fixed span 內。自然
  8-event title slice 的 builder／consumer／formatter／writer hits 都是 `0`；之後
  明確標記 `controlled-consumer` 的 fixture 取得 consumer index setup `1` 筆，actual
  index `0`、event byte `0x00`、event-array index `0`、local length `1`、caller LR
  `0x0800C735`，且 `index_less_than_table_b_count=true`。
- controlled patched receipt 的 static addressing 與 runtime hash 分欄：formatter／
  writer／codepage lookup／glyph expand 均命中；3 組 128-byte glyph cache 均從
  `0x02000000` 複製到 `0x0600C000`、`0x0600C080`、`0x0600C100`，並在 tilemap base
  `0x02013050` 取得 3 組 hash-only write receipts。runtime code unit `0x9594` 的
  codepage index `1301` 對應 U+90E8；本次其他 code units 僅記為未收錄的 identity，
  不由 addressing 或 glyph hash 推測 Unicode。
- BPS 使用共用 `core/patches/bps_create.rb`／`bps_apply.rb`：patch size `109` bytes，
  source CRC32 `a4a1c956`、target CRC32 `83398341`、patch CRC32 `e65c22d2`；BPS
  SHA-256 為 `9a9d5ed9af847dbdf9dcaa48785be76eb5a107d41f3928711faabf2d7c20726e`。
  clean ROM 套用 BPS 後與 encoder 產生的 patched ROM `cmp` 相等；patched SHA-256 為
  `d19e90027f086833be5edeaea5ffbefe59d8e17be27a59a9e9a5dde26718749a`。
- 目前本作完整 unittest suite 為 `42` 個通過，core/gba suite 為 `6` 個通過；其中
  decoder、font coverage、patcher、patch verifier 與 fixed-slot runtime contract 均有
  ROM-independent coverage。repository safety 已通過；ROM strict identity 仍保留
  header complement mismatch。

## provisional

- B0–B5 的 `zh-TW` 目標是依已查核的 Table B battle-effect label 語境建立，且刻意只用
  本機已存在的 codepage glyph；`ai_review` 仍表示需要術語與實機畫面審核。這批不是
  劇情、武將、地名、官職或完整戰役事件翻譯。
- fixed-slot insertion 的 byte-level 邊界已成立，但 formatter 的自然 caller、行寬／
  游標語意和所有控制碼契約仍未以自然畫面核對。既有 M2.3 controlled receipt 不能移植
  成這批 patched ROM 的自然 reachability 證據。
- 只有 B0–B5 使用了目前已核對的 glyph coverage；pool A/C/D、Table B 其餘 unique
  records 可能需要額外字庫／版面決策，不能由這一批的 fit 結果外推。

## negative／pending

- M2.4 的兩條 fresh-process natural path 仍是 `0` consumer cohort：都停在 title
  input-read loop，沒有 builder、consumer、formatter 或 writer hit。這批沒有新增自然
  event index `<44` 證據；controlled `actual index=0` 仍單獨標示為 controlled。
- patched B0–B5 尚未取得自然選單／戰役畫面 QA；本次 mGBA receipt 是 controlled
  consumer only，不能宣稱 B0–B5 已通過自然 runtime glyph、tilemap、版面或可玩流程
  驗收。未測畫面包括 title 以外的選單、戰役事件、劇情、武將／地名／官職與 pool
  A/C/D consumers。
- header complement mismatch（stored `0xe1`、calculated `0x13`）仍原樣保留；clean
  ROM identity 不因 BPS target receipt 而被改寫成標準 clean header。

## 可重現命令（輸出留在 ignored／暫存）

```text
ruby core/ledger/restore_translations.rb \
  games/sangokushi-eiketsuden/translations/table-b-batch-1.jsonl \
  /private/tmp/b3ej-all-source-v3.jsonl /private/tmp/b3ej-batch1-work-v3.jsonl
ruby core/ledger/strip_translations.rb \
  /private/tmp/b3ej-batch1-work-v3.jsonl /private/tmp/b3ej-batch1-stripped-v3.jsonl
cmp games/sangokushi-eiketsuden/translations/table-b-batch-1.jsonl \
  /private/tmp/b3ej-batch1-stripped-v3.jsonl
PYTHONDONTWRITEBYTECODE=1 python3 games/sangokushi-eiketsuden/tools/font_coverage.py \
  games/sangokushi-eiketsuden/roms/base/B3EJ_JP_candidate.gba \
  --work /private/tmp/b3ej-batch1-work-v3.jsonl --output /private/tmp/b3ej-batch1-font.json
PYTHONDONTWRITEBYTECODE=1 python3 games/sangokushi-eiketsuden/tools/patch_table_b.py \
  games/sangokushi-eiketsuden/roms/base/B3EJ_JP_candidate.gba \
  --work /private/tmp/b3ej-batch1-work-v3.jsonl \
  --output /private/tmp/b3ej-batch1-patched.gba \
  --metadata-output /private/tmp/b3ej-batch1-patch.json
PYTHONDONTWRITEBYTECODE=1 python3 games/sangokushi-eiketsuden/tools/verify_table_b_patch.py \
  games/sangokushi-eiketsuden/roms/base/B3EJ_JP_candidate.gba \
  /private/tmp/b3ej-batch1-patched.gba \
  --work /private/tmp/b3ej-batch1-work-v3.jsonl \
  --output /private/tmp/b3ej-batch1-verify-v3.json
ruby core/patches/bps_create.rb \
  games/sangokushi-eiketsuden/roms/base/B3EJ_JP_candidate.gba \
  /private/tmp/b3ej-batch1-patched.gba /private/tmp/b3ej-table-b-batch1.bps
ruby core/patches/bps_apply.rb \
  games/sangokushi-eiketsuden/roms/base/B3EJ_JP_candidate.gba \
  /private/tmp/b3ej-table-b-batch1.bps /private/tmp/b3ej-batch1-applied.gba
cmp /private/tmp/b3ej-batch1-patched.gba /private/tmp/b3ej-batch1-applied.gba
```

下一個邊界是先完成 patched ROM 的獨立 mGBA runtime receipt；若自然流程仍無法跨過
state gate，必須維持 negative／pending 分類並回到 state-owner／畫面觸發條件，不以
controlled fixture 擴大結論。之後才處理 Table B 其餘 unique records，再建立 pool A/C/D
的翻譯批次與全量 encoder／版面規則。
