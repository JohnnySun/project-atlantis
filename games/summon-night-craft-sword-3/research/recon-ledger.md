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
| `ROM-ID-001` | 目標是日版 GBA、game code `B3CJ` | `confirmed` | 使用者提供的 ZIP 只有一個 33554432-byte entry；`inspect_rom.py --strict` 讀得 `CRAFTSWORD H`／`B3CJ`／maker `D9`／revision `0` | 保留此 clean dump 的完整 hash，後續工具只接受同一身分 |
| `ROM-ID-002` | 本機 ROM 的容量、CRC32、header checksum | `confirmed` | `size=33554432`、`CRC32=12afae5d`、stored／calculated header checksum 均為 `6b`；與 Data Crystal 候選一致 | 不把其他 dump、patch 或不同 revision 混入 |
| `ROM-ID-003` | 本機 ROM 與公開 csm3 build/reference SHA-1 是否一致 | `confirmed` | 本機 `SHA-1=3f5253fcf57e07ce52472bd29a61d16b98a12376`，與 [csm3](https://github.com/jiangzhengwenjz/csm3) 公開 reference 一致；只作身分交叉比對 | 只參考公開工程資訊，不把反編譯資產或完整腳本帶入本作 |
| `ROM-ID-004` | ZIP 來源與 ignored extraction 邊界 | `confirmed` | ZIP 唯讀 listing 為單一 32 MiB entry；實體檔為 ignored `roms/base/B3CJ-jp-from-zip.gba`，ROM／ZIP 未 stage | 後續重跑仍使用 ignored 路徑，不在 Git 保存來源檔 |
| `TEXT-001` | 主日文點陣字型可能使用 16-bit、類 Shift-JIS 的碼值（例如 `0x8140` 起的表） | `candidate` | Data Crystal TBL 線索；本機掃描在 `0x79d26a` 找到 little-endian 179 units／134 個可解碼 unit，在 `0x145364c`、`0x145374c` 找到 113-unit runs；候選均無 ROM pointer reference | 需以反組譯、ROM-to-VRAM byte match 或文字畫面證實，不能直接建 decoder |
| `STATIC-TEXT-001` | 常見日文 probe 是否為 uncompressed script | `candidate` | direct `はい` 15 次、`セーブ` 10 次、`ロード` 4 次等命中；probe bytes 可出現在 binary／UI 資產，沒有字串邊界或 control-code 證據 | 只把 offset 留作後續定位線索，不把 probe 命中當原文表 |
| `STATIC-PTR-001` | ROM pointer table／指標 run | `candidate` | `scan_static.py` 找到 150059 個 aligned ROM-address words、1750 個至少 4 words 的 runs；這也可能是 literal pool／jump table | 需要 THUMB control-flow 或 runtime load site 交叉確認 |
| `STATIC-COMP-001` | GBA LZ77／RLE decoder 可消費的資料候選 | `candidate` | 有界掃描每種最多 2048 個 header、宣告展開上限 `0x40000`；保留 32 個最大候選，例：LZ77 file offset `0xc9f0d8`、RLE `0xc6cabc` | decoder 可消費不代表 payload 是文本；需先找到 caller／用途，再決定是否解壓 |
| `RUNTIME-001` | mGBA boot snapshot 是否能直接證實文本渲染路徑 | `blocked` | 一次性 mGBA 0.10.5 GDB snapshot 讀到 `PC=0x03003652`、`DISPCNT=0x1140`、`BG0CNT=0x0088`、`KEYINPUT=0x03ff`；沒有文字 ROM-to-VRAM match | 不再嘗試 port shim；待有可重現 scripting/headless 路徑或明確 debug 入口再開 runtime |
| `RUNTIME-002` | mGBA scripting/headless 文本偵察 | `blocked` | 已安裝 CLI 不接受 `--script`；未保留未驗證的 GUI／GDB 實驗工具 | 先解決工具能力與可重現入口，否則維持靜態候選狀態 |
| `FONT-001` | 字型位置、tile 格式、codepage 身分 | `blocked` | 尚無 glyph addressing／VRAM match；不能沿用其他遊戲格式 | 找到可重複 glyph 後，分開驗證 addressing 與 identity |
| `SOURCE-001` | 可供帳本使用的日文原文表 | `blocked` | 目前沒有已證實的 string boundary／decoder，也沒有提交原文表 | 文本結構確認後，才在 ignored `research/*-decoded.jsonl` 輸出 `string_id／locale／text／provenance` |
| `TRANSLATION-001` | 劇情、支線、夥伴、鍛造、戰鬥、道具的有限量翻譯 | `blocked` | 目前沒有可核對的本機原文與控制碼規則 | 先完成一個可回插、可 restore／strip 往返的短批次；本里程碑不宣稱已開始翻譯 |

## 第一個可重現檢查

對使用者提供的 ignored 日版 ROM 執行：

```sh
python3 games/summon-night-craft-sword-3/tools/inspect_rom.py --strict \
  games/summon-night-craft-sword-3/roms/base/B3CJ-jp-from-zip.gba
python3 games/summon-night-craft-sword-3/tools/scan_static.py \
  games/summon-night-craft-sword-3/roms/base/B3CJ-jp-from-zip.gba \
  --output games/summon-night-craft-sword-3/work/static-report.json
```

`--strict` 會把 game code、header checksum、size、CRC32 與公開 reference SHA-1 一起作門檻。這次本機 readback 的 SHA-256 是 `39bc4cf448106aa4b8cdde235632ffb57432c4b1919c8843510b70b3787fad2d`；若其他 clean dump 不同，先保留完整 hash 與差異，不修改 ROM 或用補丁檔冒充來源 ROM。`static-report.json` 是 ignored 產物，只提交工具與本帳本的摘要。

本次完整 ignored 靜態報告的 SHA-256 為 `cefdd9e0d8197b9642976ce976538a04d456d173d4837c02f6016a46a4ae0aed`；報告由上述 scanner 直接重建，不把報告或其中任何原始 bytes 加入 Git。

靜態掃描明確有界：Shift-JIS-shaped run 預設只掃 halfword alignment `0`、至少 8 個 units、最多保存 32 筆；LZ77／RLE 各最多嘗試 2048 個 header、展開上限 `0x40000`。因此「沒有候選」也不能視為全 ROM 證明；本次結果只足以把上述 offset 列為候選。

## 外部資料索引

- [Data Crystal 遊戲頁](https://datacrystal.tcrf.net/wiki/Summon_Night_Craft_Sword_Monogatari%3A_Hajimari_no_Ishi)：B3CJ、容量、CRC32 與 header checksum 的候選 metadata。
- [Data Crystal TBL](https://datacrystal.tcrf.net/wiki/Summon_Night_Craft_Sword_Monogatari%3A_Hajimari_no_Ishi/TBL)：主日文字型的公開 code-table 線索；只作工程假說，不是本機抽取結果。
- [csm3 WIP 反編譯](https://github.com/jiangzhengwenjz/csm3)：可供控制流／資料結構研究的公開工程參考；其 build/reference hash 必須與本機 ROM 分開記錄。
- [臺灣繁體 Wikipedia 條目](https://zh.wikipedia.org/wiki/%E5%8F%AC%E5%96%9A%E5%A4%9C%E9%9F%BF%E6%9B%B2_%E9%91%84%E5%8A%8D%E7%89%A9%E8%AA%9E_%EF%BD%9E%E8%B5%B7%E6%BA%90%E4%B9%8B%E7%9F%B3%EF%BD%9E)：標題與部分角色名稱的既有中文寫法參考。
- [巴哈姆特流程攻略](https://forum.gamer.com.tw/G2.php?bsn=5499&lorder=1&parent=584&sn=578)：本作流程與專有名詞的社群用語交叉參考；不把攻略內容當成 ROM 原文。

既有英文／中文 patch 只可用來核對工程方向、已知版號或 bug 線索；不可把 patch 內的翻譯腳本直接當作日文來源，也不可把 ROM、完整原始腳本或未授權字型帶進 Git。
