# 《勇者鬥惡龍怪獸篇 旅團之心》翻譯工作區

本目錄只處理日版 GBA《ドラゴンクエストモンスターズ キャラバンハート》（A9HJ）。翻譯目標是臺灣繁體 `zh-TW`；遊戲名稱採用 Wikipedia／巴哈姆特／臺灣攻略社群可交叉確認的「勇者鬥惡龍怪獸篇 旅團之心」，不把既有英文 patch 的專有名詞直接視為中文譯名。

ROM、抽出的日文原文、字型點陣、OCR／渲染圖片、工作記錄與構建產物只留在本機。可提交的 `translations/*.jsonl` 只能是 `core/ledger/strip_translations.rb` 產生的 ledger，不得帶 `source` 原文；這款新遊戲不採用兩款《黃金太陽》的既有例外格式。

## 目前狀態（2026-08-16）

- **已確認遊戲身分**：ROM 標頭為 `DQM-CARAVANH`、game code `A9HJ`、maker code `B4`、Rev.00；標頭補數校驗正確。
- **已建立可重跑的唯讀偵察工具**：`tools/recon_rom.py` 會輸出檔案指紋、標頭、Shift-JIS sentinel 命中、ROM 指標候選、BIOS 壓縮簽章統計；不輸出完整遊戲原文。
- **已建立獨立 mGBA／GDB 偵察路徑**：共享 `core/gba/capture_runtime.py` 已在 clean A9HJ 驗證 GBA 入口與首次 VRAM 寫入；此前 32 MiB candidate 的動態結果只保留為歷史負面偵察，不能作為正式 offset、codepage 或回插依據。
- **正式 clean 基準已放行**：`roms/base/Dragon_Quest_Monsters_Caravan_Heart_JP_A9HJ.gba` 為 8 MiB、CRC32 `3C24ABCC`、SHA-256 `FB388539B95FDAF6009BAD879E9BBB25955DAF8D4D438486A9213D407B2B48CE`，標頭／補數一致；`recon_rom.py` 已在此檔案重跑。
- **已在 clean ROM 收斂文本消費者與 glyph／版面路徑**：`0x08012500`／`0x0801266C` 會消費文字狀態，`0x08013738` 收到兩個 byte code unit 並透過 state `+0x04` 的 glyph table 寫入 state `+0x08` 的輸出；第二次 A 後可穩定渲染含 `さいしょからはじめる` 的 BG0 4bpp menu。可重跑工具是 `tools/trace_clean_loader.py`，完整證據與雜湊見 `research/recon-20260816.md`。
- **文字格式仍未完成**：目前只能把 codepage 標成 `custom-two-byte candidate`；腳本儲存邊界、控制碼、字寬表、完整 VWF writer、glyph identity 對照與可逆回插尚未證明。直接搜尋常見日文 Shift-JIS UI sentinel 仍為 0 命中，不能套用《黃金太陽》或《光明之魂》的格式假設。
- **尚未翻譯**：clean 基準已具備，但可逆抽取路徑、文字格式、字型／控制碼與版面仍未確認；不建立 source-bearing 工作記錄，也不宣稱英文 patch 已被本專案覆蓋或重用。

詳細數值、英文 patch 工程審計與已排除的假設見 `research/recon-20260816.md`。

## 本機工作流

將合法取得、未修改的日版 ROM 放在被忽略的 `roms/base/`，先執行：

```sh
/usr/bin/python3 games/dragon-quest-monsters-caravan-heart/tools/recon_rom.py \
  games/dragon-quest-monsters-caravan-heart/roms/base/Dragon_Quest_Monsters_Caravan_Heart_JP_A9HJ.gba
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
