# 《召喚夜響曲 鑄劍物語 ～起源之石～》工作區

本目錄只處理日版 GBA 第三代《サモンナイト クラフトソード物語 〜はじまりの石〜》（候選 game code `B3CJ`）。不修改第一代或第二代，也不把 KONKR、Project Advance、ADB 或其他裝置部署問題帶入 Project Atlantis 核心架構。

本作採用 `.agents/skills/gba-localization/SKILL.md` 與 `docs/TRANSLATION-LEDGER.md` 的新遊戲帳本流程：日文原文只在本機 `research/*-decoded.jsonl`，翻譯編輯只在本機 `work/`，可提交資料只使用 `translations/*.jsonl` 的 `source_hash` 形式。ROM、patch、渲染圖、OCR 輸出與大段掃描結果不提交。

## 目前狀態

截至 2026-08-16，已從使用者提供的日版 ZIP 唯讀取出單一 32 MiB ROM，並以 `inspect_rom.py --strict` 證實為 `B3CJ`。M1.5 與 M2.1 已完成：依固定的 csm3 callsite 鎖定 type-2 script resource table，對 LZ77／`PSI3` 資源建立有界 extractor，從 13 個 resource ID 可重抽 361 筆真實日文 record；新增控制碼保真 parser、opaque fallback、Shift-JIS source re-encode 與解壓 stream byte-identical round-trip。字型、未命名 VM opcode、完整回插 encoder 與 ROM container rebuild 仍未完成。完整狀態見 [`research/recon-ledger.md`](research/recon-ledger.md)、[`research/static-format.md`](research/static-format.md)、[`research/m2.1-control-roundtrip.md`](research/m2.1-control-roundtrip.md) 與 [`ROADMAP.md`](ROADMAP.md)。

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

這些值來自固定的 [Data Crystal 遊戲頁 oldid=69650](https://datacrystal.tcrf.net/wiki/Summon_Night_Craft_Sword_Monogatari%3A_Hajimari_no_Ishi?oldid=69650) 與 [csm3 commit `7e388ac`](https://github.com/jiangzhengwenjz/csm3/commit/7e388ac861bbac289b1f86dc5b8fa46d47b1a1a2)。若本機檔案不一致，必須保留實際 hash 並標記版號差異，不得直接覆寫或把不同版本混為同一 revision。

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

M1.5 的 bounded script extractor 另用：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 games/summon-night-craft-sword-3/tools/extract_static.py \
  games/summon-night-craft-sword-3/roms/base/B3CJ-jp-from-zip.gba \
  --output games/summon-night-craft-sword-3/research/summon-night-craft-sword-3-decoded.jsonl \
  --verify-roundtrip
```

這會驗證固定 ROM 身分，解析 type-2 table `0x1718ffc` 的 79 個 resource ID，解壓 `PSI3` stream，並把不含翻譯的日文原文與結構化控制資料寫入 ignored JSONL；`--verify-roundtrip` 只驗證解壓 PSI3 stream 與 record 層，不宣稱 LZ77／pointer／ROM 回插。工具測試與實際收據見 [`research/m2.1-control-roundtrip.md`](research/m2.1-control-roundtrip.md)；不要將該 JSONL stage。

尚未由 extractor 覆蓋的候選仍必須再經反組譯、ROM-to-VRAM byte match 或 mGBA 執行期讀取確認。共用 `core/gba/capture_runtime.py` 與 renderer 已可用，且共用測試 6 項通過；本次 B3CJ capture 仍受 runtime port 阻塞：其他 session 佔用 2345，`ports.qt.gdbPort=25352` 未建立 listener，既有 `/private/tmp` redirect dylib 的一次重用也未建立 25351。RUNTIME-003 只限制 live RAM／VRAM 交叉驗證，不否定已由本機 ROM、固定 pointer table 與 csm3 consumer 重跑的 M1.5 靜態結果；不新增遊戲專屬 GDB／dump／renderer。

## 文字系統研究邊界

外部 [Data Crystal TBL](https://datacrystal.tcrf.net/wiki/Summon_Night_Craft_Sword_Monogatari%3A_Hajimari_no_Ishi/TBL?oldid=53006) 提供主日文字型的 16-bit code-table 線索；本輪已用固定 B3CJ ROM 的多個 `0x0308 ... 0x0000` record 交叉驗證：VM halfword 仍按 little-endian 讀取，但 marker 後的 codepage bytes 必須以記憶體原始順序直接做 strict Shift-JIS decode，不能逐 halfword swap。M2.1 另以 csm3 handler／expression callsite 證實有限控制形狀，未知 word 保留 opaque；這不代表字型與所有 opcode 都已命名，也不能假設第一、二代的格式相同。完整格式見 [`research/static-format.md`](research/static-format.md) 與 [`research/m2.1-control-roundtrip.md`](research/m2.1-control-roundtrip.md)。研究時必須分開記錄：

1. 字串在哪裡、如何分界、是否有指標、壓縮與控制碼如何運作。
2. glyph 的位址／tile 定址是否已找到。
3. 每個 glyph 的 Unicode 身分是否有獨立交叉證據。

目前已建立受限的 `research/summon-night-craft-sword-3-decoded.jsonl` 作為本機原文邊界；OCR 只能作候選證據，不能直接複製到翻譯記錄。已命名控制碼可做 record/stream round-trip，但未知 opcode、字型與完整排版規則確認前，不開始劇情、支線、夥伴、鍛造、戰鬥或道具的翻譯批次。

## 翻譯帳本與術語

本作的翻譯批次必須遵循：

```text
research/*-decoded.jsonl  (本機日文原文，不提交)
        + restore_translations.rb
work/*.jsonl              (本機 source + zh-TW 工作檔，不提交)
        + strip_translations.rb
translations/*.jsonl      (可提交 ledger，只含 source_hash)
```

目標語言固定明寫為 `zh-TW`。專有名詞先查臺灣繁體 Wikipedia、巴哈姆特等多個社群來源，採既有主流寫法；若來源分裂，保留現有選擇並在 review note 說明，不自行創造音譯。既有英文／中文 patch 可參考工程資訊，但不是未審核的日文翻譯來源。

## 完成標準（M2.1 已達成，後續尚未達成）

- clean 日版 ROM 的 header、revision、CRC32、SHA-256 已記錄並可重跑。
- type-2 script table、LZ77、`PSI3` stream、bounded text record、Shift-JIS codepage 與 csm3 consumer 有遊戲專用、可重跑證據。
- 已命名控制碼的參數寬度、opaque fallback、361 筆 source re-encode 與 13 個 resource 的 decoded stream byte-identical round-trip 有收據。
- 相同 byte length 的 record-level 原地修改可行；zero padding 縮短 blocked，變長需 resource rebuild；完整 VM、字型、LZ77／pointer encoder 與 ROM 回插仍待建立。
- 至少一個有限量批次通過 `restore → work → strip` 往返與 repository safety check。
- 編碼器／回插器拒絕來源 hash、缺字、控制碼或長度不一致，而不是放寬檢查。
- 重建 ROM 重新抽取吻合；BPS round-trip 與 mGBA 核心畫面回歸另有收據。

目前已完成 clean 日版 ROM 身分／hash、M1.5 靜態 decoder、M2.1 控制碼保真 parser 與 361 筆 ignored source extraction；尚無翻譯、ROM build、BPS、字型／完整 VM／回插或 runtime QA 收據。
