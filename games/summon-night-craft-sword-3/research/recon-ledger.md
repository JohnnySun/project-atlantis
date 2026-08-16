# B3CJ 唯讀偵察帳本

本帳本只保存可公開的研究判斷、證據索引與下一個可重現檢查，不保存 ROM、抽出的原文、完整字串表、渲染圖或 OCR 結果。原文若能從本機合法 ROM 解出，固定放在被 `.gitignore` 排除的 `research/summon-night-craft-sword-3-decoded.jsonl`；實際翻譯編輯放在被排除的 `work/`；只有經 `core/ledger/strip_translations.rb` 產生、沒有 `source` 欄位的 `translations/*.jsonl` 才能提交。

## 狀態定義

- `candidate`：來自公開資料或靜態掃描，尚未由本機 ROM 或執行期資料交叉確認。
- `confirmed`：至少兩種互相獨立的證據吻合，且可由遊戲專用腳本重跑。
- `rejected`：已在指定測試情境下被反例推翻；記錄測試情境，避免下次誤用成永久結論。
- `blocked`：需要本機 ROM、模擬器執行期狀態或其他外部輸入，現階段不能安全猜測。

## 目前紀錄（2026-08-16）

| ID | 項目 | 判定 | 證據／重跑方式 | 下一步 |
| --- | --- | --- | --- | --- |
| `ROM-ID-001` | 目標是日版 GBA、game code `B3CJ` | `candidate` | Data Crystal 的遊戲頁；尚無本機 ROM readback | 對本機 ROM header `0xAC..0xAF` 做唯讀檢查 |
| `ROM-ID-002` | 公開資料列出的 32 MiB、CRC32 `12AFAE5D`、header checksum `6B` | `candidate` | Data Crystal metadata；未與本機檔案比對 | 計算本機 size／CRC32／header complement checksum |
| `ROM-ID-003` | WIP 反編譯專案提供 SHA-1 `3f5253fcf57e07ce52472bd29a61d16b98a12376` 的 build/reference ROM | `candidate` | `jiangzhengwenjz/csm3` README；不是本專案已取得的 ROM | 本機 hash 完成後只做一致性比對，不把反編譯資產直接混入本作 |
| `TEXT-001` | 主日文點陣字型可能使用 16-bit、類 Shift-JIS 的碼值（例如 `0x8140` 起的表） | `candidate` | Data Crystal TBL，來源註明 Pablitox／Ritchburn | 在乾淨 ROM 中以 little-endian／大端序兩種候選做有限量 byte scan，再以畫面字形驗證 |
| `TEXT-002` | 文本是否未壓縮、是否有 BIOS 壓縮、是否使用指標表 | `blocked` | 尚未有本機 ROM，不能由空白結果推論 | 先跑 `tools/inspect_rom.py`；再對候選位址做 THUMB 控制流與執行期交叉確認 |
| `FONT-001` | 字型位置、tile 格式、codepage 身分 | `blocked` | 沒有 ROM／VRAM 觀察；不能沿用其他遊戲的格式 | 先定位可重複 glyph，再分開記錄「glyph addressing」與「glyph identity」 |
| `SOURCE-001` | 可供帳本使用的日文原文表 | `blocked` | 目前沒有 `*-decoded.jsonl`，也沒有任何翻譯批次 | 文字結構與 codepage 確認後，輸出 `string_id／locale／text／provenance`，只留本機 |
| `TRANSLATION-001` | 劇情、支線、夥伴、鍛造、戰鬥、道具的有限量翻譯 | `blocked` | 尚未有可核對的本機原文與控制碼規則 | 先完成一個可回插、可 restore／strip 往返的短批次 |

## 第一個可重現檢查

對使用者自己的本機日版 ROM 執行：

```sh
python3 games/summon-night-craft-sword-3/tools/inspect_rom.py /path/to/B3CJ.gba
```

`--strict` 只在需要將 game code、header checksum、公開 metadata 一起作門檻時使用。若外部資料與本機 clean dump 不一致，先保留兩者的完整 hash 與差異，不修改 ROM 或用補丁檔冒充來源 ROM。

## 外部資料索引

- [Data Crystal 遊戲頁](https://datacrystal.tcrf.net/wiki/Summon_Night_Craft_Sword_Monogatari%3A_Hajimari_no_Ishi)：B3CJ、容量、CRC32 與 header checksum 的候選 metadata。
- [Data Crystal TBL](https://datacrystal.tcrf.net/wiki/Summon_Night_Craft_Sword_Monogatari%3A_Hajimari_no_Ishi/TBL)：主日文字型的公開 code-table 線索；只作工程假說，不是本機抽取結果。
- [csm3 WIP 反編譯](https://github.com/jiangzhengwenjz/csm3)：可供控制流／資料結構研究的公開工程參考；其 build/reference hash 必須與本機 ROM 分開記錄。
- [臺灣繁體 Wikipedia 條目](https://zh.wikipedia.org/wiki/%E5%8F%AC%E5%96%9A%E5%A4%9C%E9%9F%BF%E6%9B%B2_%E9%91%84%E5%8A%8D%E7%89%A9%E8%AA%9E_%EF%BD%9E%E8%B5%B7%E6%BA%90%E4%B9%8B%E7%9F%B3%EF%BD%9E)：標題與部分角色名稱的既有中文寫法參考。
- [巴哈姆特流程攻略](https://forum.gamer.com.tw/G2.php?bsn=5499&lorder=1&parent=584&sn=578)：本作流程與專有名詞的社群用語交叉參考；不把攻略內容當成 ROM 原文。

既有英文／中文 patch 只可用來核對工程方向、已知版號或 bug 線索；不可把 patch 內的翻譯腳本直接當作日文來源，也不可把 ROM、完整原始腳本或未授權字型帶進 Git。
