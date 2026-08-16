# M3 custom zh-TW glyph format gate：licensed Unifont-T fixture

日期：2026-08-16（Asia/Taipei）

本切片把已確認的 B3EJ two-plane glyph format 接到一個明確授權的 zh-TW 字形來源，
但仍只做 bounded fixture，不宣稱全遊戲字型或自然 runtime 已完成。完整字型源、ROM、
work、generated planes、patched ROM、BPS 和 verifier 輸出均留在既定路徑／ignored；本檔
只保存 mapping、hash、計數與限制。

## confirmed

- mapping file [`m3-custom-glyph-map.json`](m3-custom-glyph-map.json) 固定 17 個目前缺少
  codepage entry 的臺灣繁體字 mapping；正式 batch 已使用其中的 `經／驗`、資訊／
  menu 字形、以及 pool A 的 `效`、兵種轉換字形。每個 mapping 都指定現存 B3EJ codepage
  raw code unit 與 index；mapping 不改 ROM codepage table。
- 字形來源是倉庫既有、來源與授權已記錄的 GNU Unifont-T 17.0.05：
  `vendor/fonts/unifont/unifont_t-17.0.05.hex.gz`，SHA-256
  `c1768bd7fea203db1f419045d5a9e4d420772445e29b96c8873471d3f46c5b53`，採 SIL Open
  Font License 1.1。每個 16×16 bitmap 轉成第一組 0x20-byte source plane；第二組
  plane 明確 zero-filled，再由既有 B3EJ expander 產生 0x80-byte cache。沒有提交字形
  bytes 或圖片。
- `custom_glyph_patch.py` 僅接受 reviewed Table B／event-system pools，對 target text
  先套用明確 custom Unicode→raw-code-unit mapping，其餘字元才走 strict Shift-JIS；
  會檢查 source hash、source-text hash、format／control-byte invariant、固定槽位長度、
  codepage index／raw unit 一致性和 bounded source-table non-use。pointer table、
  codepage table、ROM size 都不能改變。
- `verify_custom_glyph_patch.py` 以 custom encoder 直接比對 re-extracted payload bytes，
  不把 custom raw code unit 誤解成普通 Shift-JIS Unicode；並逐 plane 比對 licensed
  font input、檢查 selected record／glyph spans 以外沒有變更。
- event-system D batch 2 選 6 個 unique records（含 aliases 共 12 entries）：
  `custom_glyph_count=6`、`changed_byte_count=360`、pointer／codepage table unchanged、
  custom glyph plane match `6/6`、selected re-extract `12/12`、fixed-slot `12/12`。
  clean ROM SHA-256 為 `d61e284b…f0c97b0`，fixture patched ROM SHA-256 為
  `8332f030299a422b373a87790b916e9122c9ee32b62d093c1e3c02fb34d4a3dc`。
- Table B withheld-entry fixture（B20，target 使用 `經／驗`）選 1 個 unique record：
  `custom_glyph_count=2`、`changed_byte_count=120`、pointer／codepage table unchanged、
  custom glyph plane match `2/2`、selected re-extract `1/1`、fixed-slot `1/1`。fixture
  patched ROM SHA-256 為
  `a8853a4cb529a78103c3fe4b0bb617c42dde1cfb5b174411b1091be6071d8c66`。
- pool A `system-item-class` batches 1／2／3 已使用 custom mapping 完成 bounded
  record／glyph round-trip：custom plane match 分別 `1/1`、`5/5`、`8/8`，selected
  re-extract／fixed-slot 分別 `5/5`、`6/6`、`12/12`；batch 4 使用 existing codepage，
  custom glyph count 為 `0`，但其 alias 展開後 `31/31` re-extract／fixed-slot 已完成。
- D／B 的兩個 custom fixture 都以共用 BPS builder／applier 做 byte-for-byte round-trip：
  - event-system：BPS `493` bytes，source CRC32 `a4a1c956`、target CRC32 `e3c08899`、
    patch CRC32 `a5138722`，BPS SHA-256
    `22efbb238ad5d0b406c7f6768fd9055881ddfdbfd04390b739a5d2ca40d5276b`。
  - Table B：BPS `186` bytes，source CRC32 `a4a1c956`、target CRC32 `0fe59122`、
    patch CRC32 `8ab07150`，BPS SHA-256
    `419624c1cd99958d2d45ae521078ca29a5485ad09c37ad127447b69139534120`。

## provisional

- raw code unit 的「未使用」證據只涵蓋本作四個 bounded decoded source pools；完整 ROM
  仍有相同 pair 的二進位／字庫／其他資料出現，不能把 source-pool non-use 外推成全 ROM
  non-use。正式批次必須保留 mapping、pool scope 和自然畫面 QA 的限制。
- secondary plane zero-filled 是目前使用已授權 1bpp source 的明確格式決策，不是原作
  字型美術等價證明；需在 mGBA 受控／自然畫面觀察可讀性與 palette／版面結果。
- fixture 使用的 D/B target 仍是臨時 custom-glyph gate input；在 ledger 寫入正式批次前，
  需完成人工 zh-TW wording／術語審核，並把 target ledger 經 restore→strip、schema、
  custom-aware re-extract 和 BPS QA 重跑。

## negative／pending

- 尚未在自然 menu／battle／story scene 取得 custom glyph formatter→cache→VRAM／tilemap
  receipt；既有 M2 natural cohort 仍為 0，controlled receipt 不冒充自然 reachability。
- 尚未證明這 17 個 raw code unit 在 ROM 所有未解出資料中都不會被原文使用，也尚未完成
  全池 A／B／C／D 字庫覆蓋、版面最大寬度／多行規則、控制碼與壓縮邊界。
- 尚未把 fixture ledger、generated glyph output 或 BPS 當成可發布 patch；這些輸出仍在
  ignored／`/private/tmp`。下一步是完成全池 source-safe coverage、自然畫面 runtime QA、
  full-ROM raw-code-unit audit 與正式發布 patch gate。

## 可重現命令（輸出留在 ignored／暫存）

```text
PYTHONDONTWRITEBYTECODE=1 python3 games/sangokushi-eiketsuden/tools/custom_glyph_patch.py \
  games/sangokushi-eiketsuden/roms/base/B3EJ_JP_candidate.gba --pool event-system \
  --work /private/tmp/b3ej-custom-event-work.jsonl \
  --source-table /private/tmp/b3ej-all-source-v3.jsonl \
  --mapping games/sangokushi-eiketsuden/research/m3-custom-glyph-map.json \
  --font vendor/fonts/unifont/unifont_t-17.0.05.hex.gz \
  --output /private/tmp/b3ej-custom-event-patched.gba \
  --metadata-output /private/tmp/b3ej-custom-event-patch.json
PYTHONDONTWRITEBYTECODE=1 python3 games/sangokushi-eiketsuden/tools/verify_custom_glyph_patch.py \
  games/sangokushi-eiketsuden/roms/base/B3EJ_JP_candidate.gba \
  /private/tmp/b3ej-custom-event-patched.gba --pool event-system \
  --work /private/tmp/b3ej-custom-event-work.jsonl \
  --source-table /private/tmp/b3ej-all-source-v3.jsonl \
  --mapping games/sangokushi-eiketsuden/research/m3-custom-glyph-map.json \
  --font vendor/fonts/unifont/unifont_t-17.0.05.hex.gz \
  --output /private/tmp/b3ej-custom-event-verify.json
```
