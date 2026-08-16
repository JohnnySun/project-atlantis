# 《勇者鬥惡龍怪獸篇 旅團之心》翻譯工作區

本目錄只處理日版 GBA《ドラゴンクエストモンスターズ キャラバンハート》（A9HJ）。翻譯目標是臺灣繁體 `zh-TW`；遊戲名稱採用 Wikipedia／巴哈姆特／臺灣攻略社群可交叉確認的「勇者鬥惡龍怪獸篇 旅團之心」，不把既有英文 patch 的專有名詞直接視為中文譯名。

ROM、抽出的日文原文、字型點陣、OCR／渲染圖片、工作記錄與構建產物只留在本機。可提交的 `translations/*.jsonl` 只能是 `core/ledger/strip_translations.rb` 產生的 ledger，不得帶 `source` 原文；這款新遊戲不採用兩款《黃金太陽》的既有例外格式。

## 目前狀態（2026-08-16）

- **已確認遊戲身分**：ROM 標頭為 `DQM-CARAVANH`、game code `A9HJ`、maker code `B4`、Rev.00；標頭補數校驗正確。
- **已建立可重跑的唯讀偵察工具**：`tools/recon_rom.py` 會輸出檔案指紋、標頭、Shift-JIS sentinel 命中、ROM 指標候選、BIOS 壓縮簽章統計；不輸出完整遊戲原文。
- **已建立獨立 mGBA／GDB 偵察路徑**：`tools/gdb_dynamic_recon.py` 已在 A9HJ 候選上驗證 ROM 入口、VRAM watchpoint、顯示寄存器與 live VRAM 摘要；目前只證明開機圖像／BG0 的渲染路徑，尚未證明劇本文本或 VWF。
- **基準仍未放行**：目前本機候選是 32 MiB，CRC32 `EC167D8B`、SHA-256 `98c96d1f0753d22985c89fc3dd0e80ed5cbcd93eb09f880bb4418654347f7d58`，與公開 clean dump 的 8 MiB／CRC32 `3C24ABCC` 不同。因此它只能作為「格式偵察候選」，不能作為原文表或翻譯基準。
- **尚未解出文字系統**：直接搜尋常見日文 Shift-JIS UI sentinel 全部 0 命中；結構上看似 Shift-JIS 的長片段與大量壓縮標記候選都可能是圖形／程式資料假陽性，尚未證明文本、字型、指標或壓縮路徑。
- **尚未翻譯**：在 clean A9HJ ROM 與可逆抽取路徑確認前，不建立翻譯批次、不建立 source-bearing 工作記錄，也不宣稱英文 patch 已被本專案覆蓋或重用。

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

1. 取得或由使用者提供符合 `game.yml` `expected_clean` 的 clean A9HJ 日版 ROM；不從網路下載或提交商業 ROM。
2. 在 clean ROM 上重跑 `recon_rom.py`，再以 mGBA／GDB 或其他可驗證路徑定位實際文本消費者、字型搬移與輸入畫面；候選 ROM 的動態結果只能作交叉線索。
3. 分別確認「字型位址／池已定位」與「每個 glyph 身分已核對」；不得把像素表找到誤報成 codepage 已完成。
4. 寫出遊戲專用解碼器與逆向回插器，先完成未修改內容的抽取／回插 round-trip，再做有限翻譯。
5. 只在可逆回插、字庫覆蓋、BPS round-trip 與 mGBA 場景測試都有證據後，才進入 patch 里程碑。
