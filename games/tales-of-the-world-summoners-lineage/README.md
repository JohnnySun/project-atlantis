# 《世界傳說：召喚者的血統》漢化工作區

本目錄只處理日版 GBA《テイルズ オブ ザ ワールド ～サモナーズ リネージ～》
（game code `A9PJ`），目標是臺灣繁體 `zh-TW`。ROM、patch、抽出的原文、工作記錄、
解壓資源與渲染圖片只存在於研究者本機；可提交的翻譯記錄必須遵守
[翻譯帳本方案](../../docs/TRANSLATION-LEDGER.md)，不把 `source.text` 放進 Git。

## 當前狀態

目前完成的是「ROM 身分＋唯讀結構偵察」以及有界 M1／M1.5／M1.6／M1.7／M1.8／M1.9 執行期切片；
M32 已將一條已知 name-entry 畫面 row 提升到可進最小 ledger POC 的 gate，但尚未完成有限量
翻譯或可回插的文字 patch。M1.7 在不重做 startup baseline 的前提下，
以 BG1 假名鍵盤簽名安全導航，對 `0x005E`／`0x0066` 實際命中 24-byte font record
read 與 renderer CPU VRAM store；但目的位址是 `0x060020xx/0x060023xx`，不是 BG1
`0x06004020/0x06004040`，所以 renderer transfer identity 仍是 provisional，沒有建立
source table／work ledger。M20 的 keyboard table 已另確認 row 0 首五個 mapping；其中
`0x005E=あ`、`0x0066=う` 有 runtime-backed identity，一般 text stream mapping 仍未完成。
詳見
[`research/m16-name-entry-code-unit-20260816.md`](research/m16-name-entry-code-unit-20260816.md)。
M1.7 的完整 writer／DMA／BG1 negative receipt 見
[`research/m17-font-record-to-vram-20260816.md`](research/m17-font-record-to-vram-20260816.md)。
M1.8 從 reset 觀察 BG1CNT、BG1 tile 與 DMA control：證明一個 reset-stage BIOS copy
寫入 `0x06004020`，但 hash 不是 keyboard tile；keyboard gate 受暫存 mGBA queued
packet 限制未通過，沒有把它冒充 keyboard source。完整 receipt 見
[`research/m18-bg1-asset-20260816.md`](research/m18-bg1-asset-20260816.md)。
M1.5 的圖層與 VRAM negative receipt 仍見
[`research/m15-name-entry-runtime-20260816.md`](research/m15-name-entry-runtime-20260816.md)。

M1.9 以 strict serialized GDB 在三個 fresh process 重現 keyboard gate；單一
`0x06004020` write watch 為零命中，單一 DMA3 setup/control watch 則得到非 GBA 可讀
source/destination，兩者都沒有形成可信 source→VRAM receipt。完整 metadata 與
negative boundary 見
[`research/m19-gate-transfer-20260816.md`](research/m19-gate-transfer-20260816.md)。
M20 已把 `0x08089E00 + unit*0x18` record geometry、16-bit stream reader、`0x0000`
terminator 與 `0xFF70` parser behavior candidate 做成 metadata-only probe；另以 private
M1.7 capture 對齊 BG0 destination tile 與 screenblock 座標。因 immediate post-store 與
final VRAM hash 有三筆不一致，pointer pool 仍未分類，general codepage mapping／control
semantic／glyph identity 尚未完成。
完整結論見 [`research/m20-text-record-codepage-20260816.md`](research/m20-text-record-codepage-20260816.md)。

- ROM 身分、大小與雜湊已記錄；標頭補數校驗不一致，這個異常必須保留在基準資料中。
- 全 ROM 未找到常見日文 UI 詞的 literal Shift-JIS 命中，不能把一般 Shift-JIS 當成
  已確認碼頁。
- `0x1f0000`–`0x2c0000` 是高密度 16-bit little-endian／NUL 結尾資料的候選區；
  目前只能說「像文字或表格資料」，尚未把每個指標標成文字。
- `0x4dfde4`（1,333 entries）與 `0x1acf34`（520 entries）兩張指標表的目標全部
  通過 GBA LZ77 解碼，較像圖像／字型等資源，不能拿來當劇本池。
- 外部 v0.20 IPS patch 可作工程參考；其新增資料含 LZ77 資源、字型樣資料與 16-bit
  自訂碼元，但英文譯文不是本專案的日文原文依據。
- M1 的有界擷取 receipt 見 [`research/runtime-text-capture-20260816.md`](research/runtime-text-capture-20260816.md)；
  source table 的本機 row contract 與證據門檻見 [`research/source-table-spec-20260816.md`](research/source-table-spec-20260816.md)。
- 共用 `core/gba` baseline 已確認實際 BG1／BG2／BG3 tilemap 與 startup／演出圖層可
  重建；這是 graphics path 證據，不是事件／選單文字或 codepage 證據，詳見
  [`research/runtime-baseline-core-20260816.md`](research/runtime-baseline-core-20260816.md)。
- M1.5 的互動畫面、glyph addressing、renderer 判定與兩段 bounded negative watchpoint
  receipt 見 [`research/m15-name-entry-runtime-20260816.md`](research/m15-name-entry-runtime-20260816.md)。
- M1.6 的 BG1 八格 metadata／hash、EWRAM/IWRAM diff、`0x02004014` writer／reader
  receipt 與 `0x08089E00 + code_unit * 0x18` font-record arithmetic 見
  [`research/m16-name-entry-code-unit-20260816.md`](research/m16-name-entry-code-unit-20260816.md)。
- M1.6 只確認 code-unit consumer／caller；selected BG1 glyph 的 clean-ROM aligned
  exact match 為零，confirmed glyph identity 為零，故仍不產生 source rows 或翻譯。
- M1.7 確認兩個 code unit 的 `0x08089E00 + unit*0x18` record read 與
  `0x08004C82`／`0x08004D1A` CPU VRAM consumer；BG1 `0x06004020`／`0x06004040` 的
  32-byte write watchpoint 為零且前後 hash 不變，故這是非 BG1 consumer，不能當作鍵盤
  glyph identity。DMA3 只取得不屬於該 record path 的 bounded setup receipt；控制碼仍未證明。
- M1.8 從 initial GDB stop 對 BG1CNT、`0x06004020`／`0x06004040` 與 DMA0–3
  control 做 bounded watch：BG1CNT 的 `0x0105` 設定與一個 BIOS tile write 已取得
  PC/LR/hash；該 tile hash 不等於已知 keyboard tile，DMA source/destination 因
  queued GDB payload 污染而維持 unknown。keyboard gate 未通過，confirmed identity
  仍為 `0`，font-record path 沒有共同 caller 證據，source table／ledger／翻譯仍關閉。
- M20 的 `m20_text_record_probe.py` 只輸出 record／stream metadata：完整 16-bit
  record table profile、`0x080063B6` 的 `ldrh` width evidence、另一路 `0x080048DC`
  的 8-bit packed caller、`0x0000` terminator 與 `0xFF70` line-advance candidate。
  8,066 個 pointer references／6,705 個 targets 仍標為 unclassified，沒有產生 source
  text、source rows 或翻譯。
- M20 的 `m20_glyph_screen_cross_probe.py` 確認 `0x005E`／`0x0066` 的四個 CPU-store
  destination tile 分別出現在 BG0 `(14,4)/(14,5)/(15,4)/(15,5)`；但 final VRAM 與
  store-stop hash 有三筆不同，故 renderer transfer gate 仍 provisional；keyboard
  table identity 則由 `m20_keyboard_codepage_probe.py` 獨立確認為 `0x005E=あ`、
  `0x0066=う`。
- M20 的 `m20_text_runtime_probe.py` 已留下 reset→2 秒 `0x080063E0` 無命中的 bounded
  negative；另一輪 fresh fixed-read 在初始 protocol 階段 connection failed，兩者都不
  被冒充為事件／選單文字命中。詳見 [`research/m20-text-runtime-20260816.md`](research/m20-text-runtime-20260816.md)。
- M21 的 `m21_source_decoder.py` 已能在本機從 clean A9PJ 產生被 ignore 的候選
  `research/*-decoded.jsonl`；receipt 為 7,553 個 NUL 結尾 rows，但只含目前鍵盤候選
  的 partial codepage，所有 row 仍 `eligible_for_ledger=false`，不代表翻譯已開始。詳見
  [`research/m21-private-decoder-20260816.md`](research/m21-private-decoder-20260816.md)。
- M22 對 6,705 個去重候選 target 做控制碼／空白 record aggregate audit：`0x0000`、
  `0xFF70` 與 `0x0001` 分開計數，沒有把頻率當作 semantic 或 scene proof；M23 的
  `m23_font_render.py` 已固定 16×12 record、MSB-first raster 與 line-advance layout，
  圖片只在 private／ignored 路徑產生。source table、ledger 與翻譯 gate 仍關閉。詳見
  [`research/m22-control-code-audit-20260816.md`](research/m22-control-code-audit-20260816.md)
  與 [`research/m23-font-render-20260816.md`](research/m23-font-render-20260816.md)。
- M24 將 broad pointer candidates 收窄成 46 個直接呼叫 `0x080063E0` 的 static caller rows，
  供後續全字串 raster／runtime context 對齊；28 個 distinct targets 仍含 unresolved
  halfword，全部 `eligible_for_ledger=false`。詳見
  [`research/m24-direct-callsite-decoder-20260816.md`](research/m24-direct-callsite-decoder-20260816.md)。
- M25 將 `0x000C→ー` 與 `0x00A8→ッ` 分開記為 context-provisional：分別有 table-slot、
  record hash 與 8 個 direct target 的 occurrence evidence，但 confirmed identity 增量仍
  為 0，沒有打開 source／ledger gate。詳見
  [`research/m25-context-mapping-20260816.md`](research/m25-context-mapping-20260816.md)。
- M26 審計 row 0 punctuation cluster `0x0006/08/09/0A/0C/0D`；table slot 都能重現，
  但只有部分 direct candidate occurrence，全部仍是 keyboard-layout-provisional，不當作
  control semantic 或 ledger-ready codepage。詳見
  [`research/m26-punctuation-20260816.md`](research/m26-punctuation-20260816.md)。
- M27 以 M25/M26 overlay 產生 46 個 local direct rows；只有 1 row 暫時沒有 unresolved
  halfword，但所有 mapping 仍 provisional、scene 未分類且 `eligible_for_ledger=false`，
  不會因此開始翻譯。詳見
  [`research/m27-provisional-decoder-20260816.md`](research/m27-provisional-decoder-20260816.md)。
- M28 已對 M27 的 46 個 private rows 驗證 schema、source hash 與 stable ID（0 mismatch、
  0 duplicate），但 runtime rows／eligible rows 都是 0，故 checksum gate 仍關閉。詳見
  [`research/m28-source-checksum-20260816.md`](research/m28-source-checksum-20260816.md)。
- M29 以 M19 runtime gate 的 BG0/BG1 screen hashes 與 private render 對應到
  `0x080526FE → 0x1FA4B4` 的 name-entry UI row；classification 只提升為
  `ui-name-entry` context candidate，reader breakpoint 仍未命中、confirmed glyph 增量仍為 0。
  詳見 [`research/m29-ui-row-cross-20260816.md`](research/m29-ui-row-cross-20260816.md)。
- M30 將 `0x1FA616` 的 `0xFF70` 與 M20 parser branch、`0x0000` terminator 及 M23
  private 16×12 render layout 交叉；只確認 line advance，其他 control、codepage general
  mapping 與 ledger eligibility 仍關閉。詳見
  [`research/m30-control-render-cross-20260816.md`](research/m30-control-render-cross-20260816.md)。
- M31 以既有 headless BIOS trace 盤點 39 組 `SWI 0x12` ROM→VRAM resource tuple；所有
  解壓輸出都沒有 keyboard tile-1/2 exact hash，`0x1EB044→0x06004020` 僅重現
  reset-stage `02d449…`。沒有 listener 或 live reader，故不打開 source／ledger gate。
  詳見 [`research/m31-bios-trace-rom-vram-20260816.md`](research/m31-bios-trace-rom-vram-20260816.md)。
- M32 重用 M29 工具加入固定 known-screen raster cross：同一 A9PJ ROM 的五個 bounded
  record mask 與 M19/M17 BG0 final image component `5/5` 相等，BG0 tilemap／final tile
  hash `10/10`，並與 BG1 keyboard gate `8/8` 同時成立。這只確認該 `ui-name-entry`
  row 的 5 個 glyph identity，`reader_breakpoint_hit=false`、`raw_byte_copy_confirmed=false`，
  不把 M1.7 font-record CPU renderer 與 BG1 asset 合併。詳見
  [`research/m32-known-screen-raster-row-20260816.md`](research/m32-known-screen-raster-row-20260816.md)。

## ROM 基準

完整欄位見 [`game.yml`](game.yml)。本次本機唯讀驗證得到：

| 欄位 | 值 |
| --- | --- |
| size | `8,388,608` bytes |
| title / game code / maker | `TOW SUMMLINE` / `A9PJ` / `AF` |
| CRC32 | `9c534023` |
| MD5 | `7bbd6798acfbe798d1e458938afc7a1a` |
| SHA-1 | `c7bda17313fdef597ccec98502e71c7e61281c9b` |
| SHA-256 | `b41c293fc0ed6111b7a37d960d9cd0c685e5d521a4739e0e2eaa7ff6186cfdd3` |
| header checksum / calculated | `0x32` / `0x64`（不一致） |

這表示目前手上的 dump 可以用 `A9PJ` 與雜湊辨識，但不能宣稱是標頭校驗完全乾淨的
pristine dump；後續所有抽取與測試都必須固定這組基準。

## 研究結論與限制

### 已確認

- 對齊 little-endian ROM 指標掃描找到大量指向資料區的引用；專用探針只輸出幾何與
  統計，不輸出原文。
- `probe_resource_pointer_table.py` 逐項解碼兩張大型表：`0x4dfde4` 的 1,333 個
  目標與 `0x1acf34` 的 520 個目標皆是有效 GBA LZ77，沒有標準 Shift-JIS sentinel。
- v0.20 patch 的本機套用結果從 8 MiB 增長到 `8,730,574` bytes；patch 差異中有
  8,251 段、378,567 個變更 bytes，並把 1,616 個原 ROM 指標改接到新增區。這是
  patch 工程證據，不等於 1,616 條劇本。
- 新增區 `0x800000` 起先出現可連續驗證的 LZ77 block；其後出現字型樣資料與 16-bit
  NUL 結尾資料。新增資料的確切碼頁與控制碼仍待 runtime／字形對照確認。

### 尚未確認

- 角色、地圖、事件、戰鬥資料的 record schema 與每個文字欄位的語意。
- 日文 codepage／glyph identity。16-bit code unit 的位址形式已高信心，字元身分仍
  未知；不會用英文 patch 反推日文並直接寫入翻譯。
- 換行、變數、姓名／道具插值、結束碼與其他控制碼。
- ROM → working source table → ledger → 目標 ROM 的完整可逆回插路徑。
- M32 已有 name-entry 畫面的 BG0／BG1／VRAM metadata 與 fixed record-to-raster
  cross；這只授權一條已知 UI row 的 source checksum／ledger POC，不能外推成一般
  codepage、事件文字或 live reader／byte-copy consumer。

## 外部工程參考

- [Bandai Namco 官方產品頁](https://www.bandainamcoent.co.jp/cs/list/summonerslinage/prod/index.html)：
  日文正式標題、Aseria 設定與遊戲類型。
- [v0.20 patch 專案頁](https://www.blade2187.com/projects/summoners-lineage/) 與
  [v0.20 變更說明](https://www.blade2187.com/2025/02/10/summoners-lineage-v0-20/)：
  只保留工程範圍、buffer 限制與版本狀態，不把英文內容當翻譯來源。
- [GameFAQs dialogue translation](https://gamefaqs.gamespot.com/gba/916705-tales-of-the-world-summoners-lineage/faqs/25869)：
  只可作日文語意的外部交叉參考；其作者明示是 approximate translation，不能取代
  日版原文。

zh-Wikipedia 的索引使用過「世界傳奇 召喚士的系譜」這個異名；目前未找到能在
Bahamut 交叉確認的本作條目，因此 `zh-TW` 標題仍是工作名。專有名詞表會等到
日文抽取可讀且完成多來源核對後才建立，不先自行造音譯。

## 帳本與本機流程

```text
research/summoners-lineage-decoded.jsonl  # 本機重建，含 source，已被 .gitignore 排除
work/*.jsonl                              # 本機校對工作記錄，已被 .gitignore 排除
translations/*.jsonl                      # 只提交 strip 後、不含 source 的帳本
```

預定流程：

```sh
/usr/bin/python3 games/tales-of-the-world-summoners-lineage/tools/<decoder>.py \
  <clean-A9PJ.gba> --output games/tales-of-the-world-summoners-lineage/research/summoners-lineage-decoded.jsonl
ruby core/ledger/restore_translations.rb \
  games/tales-of-the-world-summoners-lineage/translations/<batch>.jsonl \
  games/tales-of-the-world-summoners-lineage/research/summoners-lineage-decoded.jsonl \
  games/tales-of-the-world-summoners-lineage/work/<batch>.jsonl
ruby core/ledger/strip_translations.rb \
  games/tales-of-the-world-summoners-lineage/work/<batch>.jsonl \
  games/tales-of-the-world-summoners-lineage/translations/<batch>.jsonl
```

在 codepage、控制碼與 `string_id` 穩定前，不建立翻譯 batch；目前沒有可提交的
`translations/*.jsonl`。

## 工具

工具的輸入 ROM 路徑可以指向本機合法 dump；輸出是結構統計，不會把原文寫入 repo。
使用方式與重現指令見 [`tools/README.md`](tools/README.md)，研究數字與判定界線見
[`research/initial-recon-20260816.md`](research/initial-recon-20260816.md) 和
[`research/patch-engineering-20260816.md`](research/patch-engineering-20260816.md)。
