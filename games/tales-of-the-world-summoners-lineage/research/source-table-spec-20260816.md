# A9PJ 日文 source table 規格（2026-08-16）

這份文件定義 source table 的安全輸入與審核門檻，不是原文表本身。`source.text` 只能
由研究者在本機以合法 A9PJ ROM 重新產生；任何 `*-decoded.jsonl` 與 `work/` 檔案都
留在 `.gitignore` 路徑，不進 Git。

## 本機 row contract

真正完成 decoder 後，`research/summoners-lineage-decoded.jsonl` 每行至少要有：

```json
{"string_id":"<stable-id>","locale":"ja","text":"<local-only>","provenance":"<rom-hash;offsets;decoder-version>"}
```

`string_id` 必須由可重跑的 pointer／record 幾何產生，不能用抽取順序暫代。`provenance`
至少記錄 A9PJ ROM SHA-256、來源 file offset 或 pointer table、字串終止邊界、decoder
version，以及是否有 runtime context。控制碼在寫入 source table 前要正規化成帳本規定的
大寫 `{HH}` 形式；若某個 code unit 尚未能分辨成字元或控制碼，該 row 不得進入翻譯批次。

## 建立 row 的必要證據

每一條 source row 必須同時具備：

1. 原 ROM 的來源指標／record 與可重跑的 file offset。
2. 明確的 halfword／byte 邊界、終止碼、換行與插值／控制碼消費規則。
3. code unit 到 glyph 的定位證據，並把「能定位 glyph」和「知道 glyph 身分」分開記錄。
4. 至少一個獨立交叉證據：runtime consumer、控制流引用、或與畫面／tilemap 對應的
   可重現結果。單純 16-bit NUL 統計、合法指標或外部 patch bytes 都不夠。
5. 若 row 的語境標成事件、選單、角色或戰鬥，必須記錄該分類的判定依據；不能把
   候選區內所有 NUL 結尾資料自動當成劇本。

## 帳本接線

達到上述門檻後，流程固定為：

```text
clean A9PJ -> game decoder -> research/summoners-lineage-decoded.jsonl (local only)
                                      |
                                      v
translations/<batch>.jsonl (source_hash only, commit-safe)
                                      |
                                      v
restore_translations.rb -> work/<batch>.jsonl (local only)
                                      |
                                      v
strip_translations.rb -> translations/<batch>.jsonl
```

第一批只允許少量、已確認語境的短句／UI 字串；在碼頁、控制碼、長度限制與回插 round
trip 完成前，不建立 `translations/*.jsonl` 記錄，不從英文／中文 patch 反推日文，也不
把猜測放進 `review_notes`。

## 目前狀態

截至 M20，已由 M1.6／M1.7 runtime 與靜態 control-flow 共同支持
`0x08089E00 + code_unit*0x18` 的 24-byte font-record arithmetic，以及一條
`ldrh` 16-bit stream consumer；整個 unsigned 16-bit table bounds 與 record hash
profile 可由 `m20_text_record_probe.py` 重跑。`0x0000` 的終止分支與 `0xFF70` 的
skip／reset／vertical-advance parser behavior 已分開記錄，但尚未取得 runtime stream
sequence、選單／事件語境或控制碼 semantic name。

M1.7 的 `0x005E`／`0x0066` font consumer 目的位址不是 BG1 keyboard charblock，
所以 renderer transfer gate 仍未通過；但 M20 keyboard table 已確認兩個 runtime-backed
身份（`0x005E=あ`、`0x0066=う`），另有三個 row-0 table-only mapping（`0x0062=い`、
`0x006B=え`、`0x006F=お`）。這些 keyboard identity 不等於一般劇情 codepage，也不
填補 DMA／same-time tile receipt。8-bit packed caller 也不與 16-bit text stream 合併。
M20 的 8,066 pointer references／6,705 targets 仍全部是 `unclassified`，不能自動視為
劇情、地圖／事件、角色、戰鬥或 UI source。
M21 已能在本機生成被 ignore 的候選 `*-decoded.jsonl`，但所有 row 仍固定
`runtime_context=false`、`scene_role=unclassified`、`eligible_for_ledger=false`；這不是
可提交 source table，也沒有打開翻譯 gate。work ledger 維持空白是刻意的安全狀態。

M21 local decoder 的輸出 schema 另外包含 `decoder_version`、`control_candidates`、
`source_text_sha256`、`unresolved_code_units`、`mapping_status_counts`、`complete_codepage` 與
`source_text_emitted=true`。最後一個欄位只會出現在 ignored local JSONL；任何未解析
halfword 會變成 `{Uxxxx}`，`0xFF70` 會變成 `{FF70}`，因此不會把猜測文字悄悄寫入
ledger。private aggregate receipt 見 `research/m21-private-decoder-20260816.md`。

M22 的 `m22_control_code_probe.py` 只對去重候選 target 產生 unit frequency／stream hash；
`0x0000` 是 parser terminator、`0xFF70` 是 special-branch candidate、`0x0001` 是
all-zero record candidate，三者都不能單靠 static count 進入 control schema。M23 的
`m23_font_render.py` 讀同一個 24-byte record table，固定 16×12、MSB-first raster，並把
`0xFF70` 當 layout line-break candidate；PGM 是 local render artifact，不是 source table，
也不替 glyph identity 或 OCR 結果開 gate。M22 receipt 見
`research/m22-control-code-audit-20260816.md`，M23 receipt 見
`research/m23-font-render-20260816.md`。

M24 的 `m24_direct_callsite_decoder.py` 只保留直接呼叫 `0x080063E0` 的 ROM-literal
caller，stable ID 由 caller／target／bounded length 共同產生；它比 broad pointer pool
更適合做 local raster／context alignment，但 static BL caller 仍不等於 runtime scene
proof。M24 的 rows 固定 `scene_role=unclassified`、`runtime_context=false`、
`eligible_for_ledger=false`，不可直接交給 `restore_translations.rb`。

M25 再將兩個 context-derived mapping (`0x000C→ー`、`0x00A8→ッ`) 標成
`context-provisional`；table slot、record hash 與 direct target counts 是可重現 evidence，
不是 general codepage confirmation。這些候選不可覆蓋 M21 decoder 的 unknown placeholder，
直到 fresh runtime／完整句子 alignment 提供獨立 cross-check。

M26 將 row 0 punctuation cluster（`0x0006/08/09/0A/0C/0D`）標為
`keyboard-layout-provisional`，保存 table selection、record hash 與 direct occurrence
metadata；這些 units 仍不是 control schema，且不覆蓋 M21 的 unknown map。只有 runtime
renderer／完整句子 cross-check 後，才可進入 source checksum 或 ledger batch。

M27 的 provisional overlay 可在 local direct rows 中暫時顯示上述候選，但它另寫
`mapping_status`（`keyboard-layout-provisional` 或 `context-provisional-*`），不覆蓋 M21
保守 decoder，也不把「無 unresolved placeholder」誤當成完整 codepage。只有
`runtime_context=true`、scene role、control schema 與 source checksum 都通過，才可交給
`restore_translations.rb`。

M28 `m28_source_checksum_probe.py` 是這個 gate 的可重跑 audit：它可以對 provisional
local JSONL 驗證 hash／schema／ID uniqueness，但 `ledger_gate.open` 仍要求至少一條
runtime-backed、可分類、可進 ledger 的 row。M27 的 46 rows 雖然 0 hash mismatch、0
duplicate，仍不滿足這個條件。

M29 補上第一條 screen-and-static-caller correlated UI candidate：M19 的 `DISPCNT`、BG0/BG1
screenblock hash、8/8 keyboard positions 與 M27 `0x080526FE→0x1FA4B4` row 對齊，candidate
role 為 `ui-name-entry`。由於沒有 `0x080063E0` reader breakpoint hit，且 row 仍含
provisional mapping，M29 不把 `runtime_context_proof` 當成 `runtime_context=true` 的
ledger authorization。

M30 只確認一個獨立 control semantic：`0x1FA616` 在 `0x0000` terminator 前含一個
`0xFF70`，對應 M20 的 compare／skip／horizontal-reset／vertical-add branch，且與 M23
private 640×96、兩行 layout receipt 一致。這是 parser-and-render cross-check，不是 live
reader breakpoint，也不授權 variable/name/item controls、general codepage 或 ledger。

## M32 row-level gate（2026-08-16）

M32 沿用 M29 的單一 `0x080526FE → 0x1FA4B4` name-entry UI candidate，新增的是
固定 known-screen raster cross，不是新的 provisional overlay。對同一 A9PJ ROM，五個
bounded code unit 都滿足：`0x08089E00 + unit*0x18` record hash、16×12 MSB-first
record ink-mask、M19/M17 最終 BG0 image component mask，以及 BG0 screenbase 的
tilemap entry／final tile hash；結果為 record mask `5/5`、tile receipt `10/10`，並且
BG1 keyboard gate `8/8`。`0x0000` terminator 與 row 內無 `0xFF70`／其他 control
candidate 也固定記錄。

因此這一條 row 的 `glyph_identity_confirmed=5`、`scene_role=ui-name-entry`、
`eligible_for_ledger=true`，可進入第一個少量 source／ledger POC。這個 eligibility
只涵蓋該 row 的已知畫面語境，不代表 general codepage、事件／地圖／角色／戰鬥 rows
已解碼。M32 同時保留 `reader_breakpoint_hit=false` 與
`raw_byte_copy_confirmed=false`；M17 的 bounded CPU-store／final-tile audit 只有
`2/12` raw hash equality，且兩筆都是 blank tile hash，所以不能把 raster cross 寫成
ROM→VRAM byte-identical transfer。

M29 v2 的 output 仍是 metadata-only；`source_text_emitted=false`。第一個 local source
row 必須仍由私有 A9PJ decoder／固定 offset 重建，使用 M32 的 source hash／record／
screen proof 作 drift gate；提交的 `translations/*.jsonl` 只能由
`strip_translations.rb` 產生，絕不帶 `source`。

## M33 bounded target encoder／relocation gate（2026-08-16）

M33 只為 M32 已 eligible 的一列建立目標側 POC。keyboard table row 2 的 52 筆
selection order 以 record table `0x08089E00 + unit*0x18` 交叉檢查，固定 Latin 子集為
`A`–`Y`、`a`–`y`、`Z`、`z`；其 code-unit arithmetic、raster hash 與 target encoder
receipt 見 `research/m33-latin-target-reinsertion-20260816.md`。這是 target glyph
mapping，不是 general Japanese source decoder，且沒有宣稱 row-2 runtime tilemap hit。

M33 的 source／target separation gate 如下：

```text
clean source stream: preserved at original offset, source hash remains private
target stream: bounded Latin encoding + 0x0000, appended at ROM end
pointer: one known M32 caller literal rewritten
ledger: source_hash-only file remains the only tracked translation artifact
```

`m33_target_reinsertion_poc.py` 重新讀 appended stream、檢查 terminator、unresolved
unit count 與 encoded target hash；core BPS create/apply 再確認 target image equality。
因此 M33 可標記「實際文字變更的 bounded relocation／BPS POC 已通過」，但以下 gate
仍關閉：CJK／一般日文 codepage、控制碼 schema、全域 fixed-slot policy、clean source
re-extract hash stability、patched mGBA runtime QA。

## M34 bounded known-screen row gate

M34 沿同一 clean name-entry capture 補上一個有限的 static source-pointer row。工具
驗證 `0x08003E24` literal → file `0x087384` 的 10-byte terminated span，再以
`0x08089E00 + unit*0x18`、4 個 record hash、4 個 screen mask 與 8 個 BG0 tilemap/tile
hash 交叉。這使該主角姓名欄位的 4 個 code unit 達到 `known-screen` glyph identity
與 bounded `eligible_for_ledger=true`；它不是 runtime reader、DMA／CPU byte-copy 或
general keyboard tail mapping。

M34 的 row 可以在本機建立 source／working record，但提交 ledger 仍只能保留 stable ID、
source hash、scene、width／line budget、control metadata 與 terminology status。source
span、record rows、圖片與完整原文不可進 Git。若 keyboard selection slot 與 known-screen
identity 不一致，必須維持兩個欄位，不得用 table slot 自動覆寫 identity。

M34 private row 的 restore→strip 已以 source hash equality、stable ID equality 與
`source` key absence 驗證；`m33_target_reinsertion_poc.py --profile m34` 另證明一個
14-byte terminated target relocation 與 BPS apply equality。這兩項只代表 bounded plumbing
可重跑，不代表 general codepage、fixed-slot policy 或 patched runtime 可用。

## M35 fixed known-screen decoder

`m21_source_decoder.py --known-ui-only` 是目前唯一允許把 row-level known-screen proof
重建成 private source table 的 bounded decoder mode。它固定兩個 stable ID、offset、
terminator、code-unit sequence、record/screen provenance 與 source hash；任何 ROM drift
都 fail closed。其輸出可交給 restore／strip，但 `codepage_status` 必須保持
`bounded-known-screen-only`，不能拿 `complete_codepage=true` 解讀成 general Japanese/CJK
mapping。broad candidate mode 的 rows 仍是 `unclassified`／`eligible_for_ledger=false`。
