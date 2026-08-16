# 《召喚夜響曲 鑄劍物語 ～起源之石～》工作區

本目錄只處理日版 GBA 第三代《サモンナイト クラフトソード物語 〜はじまりの石〜》（候選 game code `B3CJ`）。不修改第一代或第二代，也不把 KONKR、Project Advance、ADB 或其他裝置部署問題帶入 Project Atlantis 核心架構。

本作採用 `.agents/skills/gba-localization/SKILL.md` 與 `docs/TRANSLATION-LEDGER.md` 的新遊戲帳本流程：日文原文只在本機 `research/*-decoded.jsonl`，翻譯編輯只在本機 `work/`，可提交資料只使用 `translations/*.jsonl` 的 `source_hash` 形式。ROM、patch、渲染圖、OCR 輸出與大段掃描結果不提交。

## 目前狀態

截至 2026-08-16，已從使用者提供的日版 ZIP 唯讀取出單一 32 MiB ROM，並以 `inspect_rom.py --strict` 證實為 `B3CJ`。已完成有界的 halfword-aligned Shift-JIS 形狀、指標 run 與 LZ77／RLE decoder-candidate 掃描；這些結果仍只是文本／資料候選，尚未證實字串邊界、控制碼、字型或回插路徑。完整狀態見 [`research/recon-ledger.md`](research/recon-ledger.md) 與 [`ROADMAP.md`](ROADMAP.md)。

### ROM metadata／外部比對

| 欄位 | 公開參考值 | 本專案狀態 |
| --- | --- | --- |
| Game code | `B3CJ` | 本機 header 已確認 |
| Header title | `CRAFTSWORD H` | 本機 header 已確認 |
| ROM size | 32 MiB | 本機檔案已確認 |
| CRC32 | `12AFAE5D` | 本機檔案已確認 |
| GBA header checksum | `6B` | stored／calculated 均為 `6B` |
| 本機 SHA-256 | `39bc4cf448106aa4b8cdde235632ffb57432c4b1919c8843510b70b3787fad2d` | 已確認 |
| 公開反編譯 build/reference SHA-1 | `3f5253fcf57e07ce52472bd29a61d16b98a12376` | 只作外部比對，不能代替本機 clean ROM |

這些值來自 [Data Crystal 遊戲頁](https://datacrystal.tcrf.net/wiki/Summon_Night_Craft_Sword_Monogatari%3A_Hajimari_no_Ishi) 與 [csm3 反編譯專案](https://github.com/jiangzhengwenjz/csm3)。若本機檔案不一致，必須保留實際 hash 並標記版號差異，不得直接覆寫或把不同版本混為同一 revision。

## 唯讀偵察

遊戲專用工具只讀檔案，不產生或修改 ROM。ZIP 內的 ROM 已放在被 Git ignore 的 `roms/base/`，不會提交：

```sh
python3 games/summon-night-craft-sword-3/tools/inspect_rom.py --strict \
  games/summon-night-craft-sword-3/roms/base/B3CJ-jp-from-zip.gba
```

它會輸出：

- GBA header title、game code、maker code、revision byte 與 complement checksum。
- 檔案大小、CRC32、MD5、SHA-1、SHA-256。
- 有界的 Shift-JIS 常見詞 probe 命中位置；命中只算線索，不算日文文本。
- ROM 位址指標 run、Thumb `swi` 候選與 GBA 壓縮 header 候選的摘要。

有限量靜態掃描另用：

```sh
python3 games/summon-night-craft-sword-3/tools/scan_static.py \
  games/summon-night-craft-sword-3/roms/base/B3CJ-jp-from-zip.gba \
  --output games/summon-night-craft-sword-3/work/static-report.json
```

它只保留候選 offset、長度、計數、pointer reference、decoder consumed size 與 SHA-256；預設掃描 halfword alignment `0`，Shift-JIS-shaped run 至少 8 個 16-bit units，LZ77／RLE 每種最多嘗試 2048 個 header 且 expanded size 上限為 `0x40000`。`work/static-report.json` 是重跑用 ignored 產物，不是提交內容。

靜態候選必須再經反組譯、ROM-to-VRAM byte match 或 mGBA 執行期讀取確認。共用 `core/gba/capture_runtime.py` 與 renderer 已可用，且共用測試 6 項通過；本次 B3CJ capture 仍受 runtime port 阻塞：其他 session 佔用 2345，`ports.qt.gdbPort=25352` 未建立 listener，既有 `/private/tmp` redirect dylib 的一次重用也未建立 25351。除了先前一次 boot register／背景設定快照外，沒有新的文本或 VRAM 對應，因此不把候選升格為已證實文本，也不新增遊戲專屬 GDB／dump／renderer。尤其不能因為某段 bytes 能被 Shift-JIS 解碼，或某個半字看起來像 BIOS `swi`，就推論它是文本或壓縮器呼叫。

## 文字系統研究邊界

外部 [Data Crystal TBL](https://datacrystal.tcrf.net/wiki/Summon_Night_Craft_Sword_Monogatari%3A_Hajimari_no_Ishi/TBL) 提供主日文字型的 16-bit code-table 線索，包含類似 `0x8140` 起始的標記；這是待驗證假說，不能直接套入 GBA little-endian ROM，也不能假設第一、二代的格式相同。研究時必須分開記錄：

1. 字串在哪裡、如何分界、是否有指標、壓縮與控制碼如何運作。
2. glyph 的位址／tile 定址是否已找到。
3. 每個 glyph 的 Unicode 身分是否有獨立交叉證據。

只有三者足夠穩定後，才建立本機 `research/summon-night-craft-sword-3-decoded.jsonl`；OCR 只能作候選證據，不能直接複製到翻譯記錄。控制碼與排版規則確認前，不開始劇情、支線、夥伴、鍛造、戰鬥或道具的翻譯批次。

## 翻譯帳本與術語

本作的翻譯批次必須遵循：

```text
research/*-decoded.jsonl  (本機日文原文，不提交)
        + restore_translations.rb
work/*.jsonl              (本機 source + zh-Hans + zh-TW 工作檔，不提交)
        + strip_translations.rb
translations/*.jsonl      (可提交 ledger，只含 source_hash)
```

目標語言固定明寫為 `zh-Hans` 與 `zh-TW`。專有名詞先查臺灣繁體 Wikipedia、巴哈姆特等多個社群來源，採既有主流寫法；若來源分裂，保留現有選擇並在 review note 說明，不自行創造音譯。既有英文／中文 patch 可參考工程資訊，但不是未審核的日文翻譯來源。

## 完成標準（尚未達成）

- clean 日版 ROM 的 header、revision、CRC32、SHA-256 已記錄並可重跑。
- 文本、字型、codepage、指標／壓縮／控制碼與可逆回插路徑有遊戲專用證據。
- 至少一個有限量批次通過 `restore → work → strip` 往返與 repository safety check。
- 編碼器／回插器拒絕來源 hash、缺字、控制碼或長度不一致，而不是放寬檢查。
- 重建 ROM 重新抽取吻合；BPS round-trip 與 mGBA 核心畫面回歸另有收據。

目前已完成 clean 日版 ROM 身分／hash 與有限量靜態偵察；尚無文本 decoder、翻譯、ROM build、BPS 或 runtime QA 收據。
