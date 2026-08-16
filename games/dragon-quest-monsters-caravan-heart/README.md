# 《勇者鬥惡龍怪獸篇 旅團之心》翻譯工作區

本目錄只處理日版 GBA《ドラゴンクエストモンスターズ キャラバンハート》（A9HJ）。翻譯目標是臺灣繁體 `zh-TW`；遊戲名稱採用 Wikipedia／巴哈姆特／臺灣攻略社群可交叉確認的「勇者鬥惡龍怪獸篇 旅團之心」，不把既有英文 patch 的專有名詞直接視為中文譯名。

ROM、抽出的日文原文、字型點陣、OCR／渲染圖片、工作記錄與構建產物只留在本機。可提交的 `translations/*.jsonl` 只能是 `core/ledger/strip_translations.rb` 產生的 ledger，不得帶 `source` 原文；這款新遊戲不採用兩款《黃金太陽》的既有例外格式。

## 目前狀態（2026-08-16）

- **已確認遊戲身分**：ROM 標頭為 `DQM-CARAVANH`、game code `A9HJ`、maker code `B4`、Rev.00；標頭補數校驗正確。
- **已建立可重跑的唯讀偵察工具**：`tools/recon_rom.py` 會輸出檔案指紋、標頭、Shift-JIS sentinel 命中、ROM 指標候選、BIOS 壓縮簽章統計；不輸出完整遊戲原文。
- **已建立獨立 mGBA／GDB 偵察路徑**：共享 `core/gba/capture_runtime.py` 已在 clean A9HJ 驗證 GBA 入口與首次 VRAM 寫入；此前 32 MiB candidate 的動態結果只保留為歷史負面偵察，不能作為正式 offset、codepage 或回插依據。
- **正式 clean 基準已放行**：`roms/base/Dragon_Quest_Monsters_Caravan_Heart_JP_A9HJ.gba` 為 8 MiB、CRC32 `3C24ABCC`、SHA-256 `FB388539B95FDAF6009BAD879E9BBB25955DAF8D4D438486A9213D407B2B48CE`，標頭／補數一致；`recon_rom.py` 已在此檔案重跑。
- **已在 clean ROM 收斂文本消費者與 glyph／版面路徑**：`0x08012500`／`0x0801266C` 會消費文字狀態，`0x08013738` 收到兩個 byte code unit 並透過 state `+0x04` 的 glyph table 寫入 state `+0x08` 的輸出；第二次 A 後可穩定渲染含 `さいしょからはじめる` 的 BG0 4bpp menu。可重跑工具是 `tools/trace_clean_loader.py`，完整證據與雜湊見 `research/recon-20260816.md`。
- **已建立 clean-only script pointer extractor**：`tools/extract_text.py` 會驗證 8 MiB／CRC32／SHA-256 後，依 `0x08266240` 三層指標表輸出本機 `*-decoded.jsonl`；輸出含 raw hex，永遠留在 ignored `research/` 或 `/private/tmp`，不是可提交翻譯來源。第一次 clean run 已驗證 pointer table 與 runtime glyph pair 交叉一致。
- **已量化 script boundary 候選**：`tools/profile_script_records.py` 只輸出聚合統計；以目前 `0x10000` max-span clean run 找到 36,509/37,600 spans 含 `FF` 候選、1,091 筆不含，且 318 筆在第一個 `FF` 後仍有 558,656 bytes。故 `FF` 目前只能標成 candidate，不能切斷 source record。
- **已建立保守的本機 source-table stage**：`tools/build_source_table.py` 只接受同一 clean hash 的 extractor output；已核對 ASCII／平假名、`0x5B..0x8F` 的 katakana atlas 順序、公開字碼表所列的 `0x94..0xBD` direct punctuation／UI units、`0x59=を`／`0x5A=ん`／`0x90=ヲ`／`0x91=ン`，以及只對已知假名 base 解出的 `0x92`／`0x93` 濁音 pair 會轉為本機文字，未知 glyph 轉 `{Uxx}`／`{Uxxxx}`，控制候選轉大寫 `{HH}`。v5 clean run 的統計由工具重算，且所有 rows 固定 `ledger_eligible=false`；因此它是 decoder 中間層，不是可提交翻譯來源。
- **已建立 clean control-dispatch audit**：`tools/audit_control_dispatch.py` 驗證 parser literal `0x08012780` 指向的 33-entry table `0x08012784`，並輸出 handler 位址與靜態 source-parameter shape；這些 shape 仍不是控制碼語義或完整 encoder。
- **已固定控制碼參數消費邊界**：`tools/audit_control_consumption.py` 在同一 clean hash 上核對 24 個 Thumb source-read signatures，將 `DF..FF` 分為 `none`、`fixed-1`、`conditional-1`、`conditional-2`；其中 `E0/E1` 的 alternate-glyph index 與 control dispatch 分支仍分開記錄。因為多個 handler 依 state flags 改變消費路徑，`extract_text.py` 暫不盲目吞取參數；完整 context decoder 仍未完成，receipt 見 `research/control-consumption-20260816.md`。
- **已建立 source-free codepage inventory**：`tools/audit_codepage_inventory.py` 只讀取 ignored raw-token JSONL，驗證 clean hash 後輸出 direct／pair／alternate／control 的聚合頻率與使用索引，不輸出原始文字；37,600 records、103,209 pair tokens、39,225 alternate-glyph tokens、217,774 control candidates 的可重跑 receipt 見 `research/codepage-inventory-20260816.md`。這是使用範圍盤點，不是完整 codepage 或控制碼解碼。
- **已固定 glyph writer／DMA3／layout 的 clean 靜態 receipt**：`tools/audit_text_layout.py` 驗證 `0x08013738`／`0x08013E00` 的單／雙 glyph 路徑、8-word OR 合成、state `+0x10` 控制的 32／64-byte stride、`0x040000D4` DMA3 複製與 `0x08013E4C` layout branch；另證明 `E0`／`E1` 一 byte alt-glyph consumer 使用 pool `0x082E0BD4`，並由 lead 分流 base／`+0x4000` 第二 bank。這界定了回寫風險，但尚未證明完整 VWF 寬度、換行或溢位語義。
- **已完成穩定 menu 的 code-unit cross-check**：`tools/verify_menu_glyphs.py` 將 clean menu dump 的十個連續 glyph tile 與同一 ROM glyph table 逐 tile 比對，並核對 pointer `0x0828647C` 的本機 script prefix；得到九個 single units 與一組 `0x92 0x34` pair，十個位置皆 matched。這是已知畫面內容的局部 identity 證據，不是完整 codepage。
- **已完成一筆局部 glyph output round-trip**：`tools/verify_glyph_output.py` 以 clean glyph table、script record 與本機 VRAM dump 重建 `0x0828667D` 的 38 個 tile；納入 `0x08013738` 的 pair masks 後達到 38/38 exact。這只驗證 glyph writer／局部版面，不代表完整 script encoder 或回插已完成。
- **文字格式仍未完成**：目前只能把 codepage 標成 `custom-mixed-byte candidate`；`0x92`／`0x93` 是已證明的雙 byte glyph lead，`0xE0`／`0xE1` 是已證明的 alt-glyph lead，其他 `<=0xDE` byte 另走單 byte glyph 路徑，`0xDF..0xFF` 是 control dispatch 候選。腳本儲存邊界、控制碼、alt pool glyph identity、字寬表、完整 VWF writer 與可逆回插尚未證明。直接搜尋常見日文 Shift-JIS UI sentinel 仍為 0 命中，不能套用《黃金太陽》或《光明之魂》的格式假設。
- **尚未全量翻譯**：clean 基準已具備，並已建立三筆 bounded source-free ledger 與含 alt-glyph placeholder 的本機 extractor／source-table stage；可逆抽取路徑、文字格式、完整字型／控制碼與版面仍未確認，不把 bounded proof 宣稱為全遊戲覆蓋，也不宣稱英文 patch 已被本專案覆蓋或重用。

詳細數值、英文 patch 工程審計與已排除的假設見 `research/recon-20260816.md`。

## 本機工作流

將合法取得、未修改的日版 ROM 放在被忽略的 `roms/base/`，先執行：

```sh
/usr/bin/python3 games/dragon-quest-monsters-caravan-heart/tools/recon_rom.py \
  games/dragon-quest-monsters-caravan-heart/roms/base/Dragon_Quest_Monsters_Caravan_Heart_JP_A9HJ.gba

/usr/bin/python3 games/dragon-quest-monsters-caravan-heart/tools/extract_text.py \
  games/dragon-quest-monsters-caravan-heart/roms/base/Dragon_Quest_Monsters_Caravan_Heart_JP_A9HJ.gba \
  --out games/dragon-quest-monsters-caravan-heart/research/dragon-quest-monsters-caravan-heart-decoded.jsonl

/usr/bin/python3 games/dragon-quest-monsters-caravan-heart/tools/profile_script_records.py \
  games/dragon-quest-monsters-caravan-heart/roms/base/Dragon_Quest_Monsters_Caravan_Heart_JP_A9HJ.gba \
  games/dragon-quest-monsters-caravan-heart/research/dragon-quest-monsters-caravan-heart-decoded.jsonl \
  --out /private/tmp/dqmch-script-profile.json

/usr/bin/python3 games/dragon-quest-monsters-caravan-heart/tools/audit_control_dispatch.py \
  games/dragon-quest-monsters-caravan-heart/roms/base/Dragon_Quest_Monsters_Caravan_Heart_JP_A9HJ.gba

/usr/bin/python3 games/dragon-quest-monsters-caravan-heart/tools/audit_text_layout.py \
  games/dragon-quest-monsters-caravan-heart/roms/base/Dragon_Quest_Monsters_Caravan_Heart_JP_A9HJ.gba

/usr/bin/python3 games/dragon-quest-monsters-caravan-heart/tools/build_source_table.py \
  games/dragon-quest-monsters-caravan-heart/roms/base/Dragon_Quest_Monsters_Caravan_Heart_JP_A9HJ.gba \
  games/dragon-quest-monsters-caravan-heart/research/dragon-quest-monsters-caravan-heart-decoded.jsonl \
  --out games/dragon-quest-monsters-caravan-heart/research/dragon-quest-monsters-caravan-heart-source-decoded.jsonl
```

文字系統確認後，遊戲專用解碼器才可產生本機原文表：

```text
games/dragon-quest-monsters-caravan-heart/research/dragon-quest-monsters-caravan-heart-decoded.jsonl  # 本機原文表，忽略
games/dragon-quest-monsters-caravan-heart/work/*.jsonl                                                    # 本機工作記錄，忽略
games/dragon-quest-monsters-caravan-heart/translations/*.jsonl                                            # 可提交 ledger，禁止 source
```

第一批翻譯必須是有限、可重現且可達的 UI／系統／一個事件場景；以 `restore_translations.rb` 重建工作記錄、填入明確的 `zh-Hans` 與 `zh-TW`，再以 `strip_translations.rb` 產生 ledger。控制碼、換行、字寬與字型映射在文字引擎確認前均視為未知，不得套用《黃金太陽》的 `{HH}` 慣例。

## 目前已知的門檻

1. **已完成**：取得並核准符合 `game.yml` `expected_clean` 的 clean A9HJ 日版 ROM；32 MiB candidate 不再作正式基準。
2. 在 clean ROM 上以 `tools/trace_clean_loader.py` 與共享 GBA runtime 工具重現文本消費者、glyph table、控制／版面分支與 title／menu／事件畫面；候選 ROM 的動態結果只能作歷史交叉線索。
3. 分別確認「字型位址／池已定位」與「每個 glyph 身分已核對」；目前前者有 clean runtime 證據，後者仍未完成，不得把像素表找到誤報成 codepage 已完成。
4. 寫出遊戲專用解碼器與逆向回插器，先完成未修改內容的抽取／回插 round-trip，再做有限翻譯。
5. 只在可逆回插、字庫覆蓋、BPS round-trip 與 mGBA 場景測試都有證據後，才進入 patch 里程碑。
