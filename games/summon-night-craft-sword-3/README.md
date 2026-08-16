# 《召喚夜響曲 鑄劍物語 ～起源之石～》工作區

本目錄只處理日版 GBA 第三代《サモンナイト クラフトソード物語 〜はじまりの石〜》（候選 game code `B3CJ`）。不修改第一代或第二代，也不把 KONKR、Project Advance、ADB 或其他裝置部署問題帶入 Project Atlantis 核心架構。

本作採用 `.agents/skills/gba-localization/SKILL.md` 與 `docs/TRANSLATION-LEDGER.md` 的新遊戲帳本流程：日文原文只在本機 `research/*-decoded.jsonl`，翻譯編輯只在本機 `work/`，可提交資料只使用 `translations/*.jsonl` 的 `source_hash` 形式。ROM、patch、渲染圖、OCR 輸出與大段掃描結果不提交。

## 目前狀態

截至 2026-08-16，已完成工作區 bootstrap、外部工程線索登錄與唯讀 ROM 檢查器；本機常見工作區、掛載磁碟與暫存目錄沒有找到 `B3CJ` 或本作檔名，因此尚未完成 ROM header／CRC／SHA-256 readback，也沒有宣稱文字系統或翻譯可行。完整狀態見 [`research/recon-ledger.md`](research/recon-ledger.md) 與 [`ROADMAP.md`](ROADMAP.md)。

### 外部候選 metadata（未經本機驗證）

| 欄位 | 公開參考值 | 本專案狀態 |
| --- | --- | --- |
| Game code | `B3CJ` | 目標候選，待 header readback |
| Header title | `CRAFTSWORD H` | 待本機 readback |
| ROM size | 32 MiB | 待本機檔案確認 |
| CRC32 | `12AFAE5D` | 待本機檔案確認 |
| GBA header checksum | `6B` | 待本機檔案確認 |
| 公開反編譯 build/reference SHA-1 | `3f5253fcf57e07ce52472bd29a61d16b98a12376` | 只作外部比對，不能代替本機 clean ROM |

這些值來自 [Data Crystal 遊戲頁](https://datacrystal.tcrf.net/wiki/Summon_Night_Craft_Sword_Monogatari%3A_Hajimari_no_Ishi) 與 [csm3 反編譯專案](https://github.com/jiangzhengwenjz/csm3)。若本機檔案不一致，必須保留實際 hash 並標記版號差異，不得直接覆寫或把不同版本混為同一 revision。

## 唯讀偵察

第一個遊戲專用工具只讀檔案，不產生或修改 ROM：

```sh
python3 games/summon-night-craft-sword-3/tools/inspect_rom.py /path/to/legally-dumped-japanese-rom.gba
```

它會輸出：

- GBA header title、game code、maker code、revision byte 與 complement checksum。
- 檔案大小、CRC32、MD5、SHA-1、SHA-256。
- 有界的 Shift-JIS 常見詞 probe 命中位置；命中只算線索，不算日文文本。
- ROM 位址指標 run、Thumb `swi` 候選與 GBA 壓縮 header 候選的摘要。

靜態候選必須再經反組譯、ROM-to-VRAM byte match 或 mGBA 執行期讀取確認。尤其不能因為某段 bytes 能被 Shift-JIS 解碼，或某個半字看起來像 BIOS `swi`，就推論它是文本或壓縮器呼叫。

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

目前只完成第一項的工具準備，尚無翻譯、ROM build、BPS 或 runtime QA 收據。
