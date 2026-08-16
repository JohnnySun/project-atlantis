# 《勇者鬥惡龍怪獸篇 旅團之心》翻譯工作區

本目錄只處理日版 GBA《ドラゴンクエストモンスターズ キャラバンハート》（A9HJ）。翻譯目標是臺灣繁體 `zh-TW`；遊戲名稱採用 Wikipedia／巴哈姆特／臺灣攻略社群可交叉確認的「勇者鬥惡龍怪獸篇 旅團之心」，不把既有英文 patch 的專有名詞直接視為中文譯名。

ROM、抽出的日文原文、字型點陣、OCR／渲染圖片、工作記錄與構建產物只留在本機。可提交的 `translations/*.jsonl` 只能是 `core/ledger/strip_translations.rb` 產生的 ledger，不得帶 `source` 原文；這款新遊戲不採用兩款《黃金太陽》的既有例外格式。

## 目前狀態（2026-08-16）

- **已確認遊戲身分**：ROM 標頭為 `DQM-CARAVANH`、game code `A9HJ`、maker code `B4`、Rev.00；標頭補數校驗正確。
- **已建立可重跑的唯讀偵察工具**：`tools/recon_rom.py` 會輸出檔案指紋、標頭、Shift-JIS sentinel 命中、ROM 指標候選、BIOS 壓縮簽章統計；不輸出完整遊戲原文。
- **已建立獨立 mGBA／GDB 偵察路徑**：共享 `core/gba/capture_runtime.py` 已在 clean A9HJ 驗證 GBA 入口與首次 VRAM 寫入；此前 32 MiB candidate 的動態結果只保留為歷史負面偵察，不能作為正式 offset、codepage 或回插依據。
- **正式 clean 基準已放行**：`roms/base/Dragon_Quest_Monsters_Caravan_Heart_JP_A9HJ.gba` 為 8 MiB、CRC32 `3C24ABCC`、SHA-256 `FB388539B95FDAF6009BAD879E9BBB25955DAF8D4D438486A9213D407B2B48CE`，標頭／補數一致；`recon_rom.py` 已在此檔案重跑。
- **已收斂一條候選版 runtime consumer 證據**：共用 GDB client 追到 `KEYINPUT` 輪詢與 BIOS `CpuSet` 的 BG char-data 搬移，並回溯到候選 ROM caller；這是輸入／tile loader 證據，不是 clean ROM 的 codepage、glyph identity 或 VWF 證據，詳見 `research/recon-20260816.md`。
- **尚未解出文字系統**：直接搜尋常見日文 Shift-JIS UI sentinel 全部 0 命中；結構上看似 Shift-JIS 的長片段與大量壓縮標記候選都可能是圖形／程式資料假陽性，尚未證明文本、字型、指標或壓縮路徑。
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
2. 在 clean ROM 上重跑 `recon_rom.py`，再以 mGBA／GDB 或其他可驗證路徑定位實際文本消費者、字型搬移與輸入畫面；候選 ROM 的動態結果只能作歷史交叉線索。
3. 分別確認「字型位址／池已定位」與「每個 glyph 身分已核對」；不得把像素表找到誤報成 codepage 已完成。
4. 寫出遊戲專用解碼器與逆向回插器，先完成未修改內容的抽取／回插 round-trip，再做有限翻譯。
5. 只在可逆回插、字庫覆蓋、BPS round-trip 與 mGBA 場景測試都有證據後，才進入 patch 里程碑。
