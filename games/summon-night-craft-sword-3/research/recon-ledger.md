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
| `EXT-001` | Data Crystal 遊戲頁／TBL 的固定版本與使用界線 | `confirmed` | 固定 [遊戲頁 oldid=69650](https://datacrystal.tcrf.net/wiki/Summon_Night_Craft_Sword_Monogatari%3A_Hajimari_no_Ishi?oldid=69650)、[TBL oldid=53006](https://datacrystal.tcrf.net/wiki/Summon_Night_Craft_Sword_Monogatari%3A_Hajimari_no_Ishi/TBL?oldid=53006)；[Community](https://datacrystal.tcrf.net/wiki/Data_Crystal/Community) 說明站內資料的 GFDL 基礎；shell raw fetch 403，未把 HTML 快取進 repo | 只保存 oldid、格式結論與 provenance，不匯入整份表格 |
| `EXT-002` | csm3 固定 revision、license review 與本機身分 | `confirmed` | 固定 commit `7e388ac861bbac289b1f86dc5b8fa46d47b1a1a2`；`csm3.sha1` 與本機 ROM SHA-1 一致；固定 checkout 未找到 root LICENSE/COPYING/NOTICE，僅於 `/private/tmp/csm3-review-b3cj` 唯讀 review | 不提交第三方 source／資產；只保留 callsite 與 commit 索引 |
| `TEXT-001` | 主日文點陣字型可能使用 16-bit、類 Shift-JIS 的碼值（例如 `0x8140` 起的表） | `candidate` | Data Crystal TBL 線索；本機掃描在 `0x79d26a` 找到 little-endian 179 units／134 個可解碼 unit，在 `0x145364c`、`0x145374c` 找到 113-unit runs；候選均無 ROM pointer reference | 需以反組譯、ROM-to-VRAM byte match 或文字畫面證實，不能直接建 decoder |
| `STATIC-TEXT-001` | 常見日文 probe 是否為 uncompressed script | `candidate` | direct `はい` 15 次、`セーブ` 10 次、`ロード` 4 次等命中；probe bytes 可出現在 binary／UI 資產，沒有字串邊界或 control-code 證據 | 只把 offset 留作後續定位線索，不把 probe 命中當原文表 |
| `STATIC-PTR-001` | ROM pointer table／指標 run | `candidate` | `scan_static.py` 找到 150059 個 aligned ROM-address words、1750 個至少 4 words 的 runs；這也可能是 literal pool／jump table | 需要 THUMB control-flow 或 runtime load site 交叉確認 |
| `STATIC-COMP-001` | GBA LZ77／RLE decoder 可消費的資料候選 | `candidate` | 有界掃描每種最多 2048 個 header、宣告展開上限 `0x40000`；保留 32 個最大候選，例：LZ77 file offset `0xc9f0d8`、RLE `0xc6cabc` | decoder 可消費不代表 payload 是文本；需先找到 caller／用途，再決定是否解壓 |
| `STATIC-SCRIPT-001` | csm3 導向的 type-2 script resource table 與 16-byte pointer units | `confirmed` | `gUnk_09718FFC` 位於 file `0x1718ffc`、大小 `0x284`，解析 ID `0..78`；`src/main.c:480-505` 的 pointer resolver 與本機 table entries 共同重現 payload；`tools/extract_static.py` 對 resource 9、12、14、24 等成功落址 | 以固定 table 續分類劇情／支線／夥伴／鍛造／戰鬥／道具群組 |
| `STATIC-SCRIPT-002` | LZ77 → `PSI3` → `+0x10` halfword stream | `confirmed` | csm3 `src/script.c:51-63` 呼叫 `LZ77UnCompWram`，`src/script.c:78-88` 消費 buffer `+0x10`；本機 bounded decoder 讀到 `PSI3` 並以 MSB-first flags 解壓 13 個 resource IDs | 繼續命名其他 VM opcode，不把 dispatch table 當文字指標表 |
| `STATIC-CODEPAGE-001` | bounded `0x0308 ... 0x0000` record 的 codepage | `confirmed` | 13 個 resource IDs 共 361 筆；marker／terminator 以 little-endian halfword 識別，marker 後 raw bytes 以原始記憶體順序 strict Shift-JIS decode；多筆 raw length／SHA-256 可重現，並與固定 TBL 線索交叉核對 | M2.2 已另以 font lookup／cell／identity 證據接上；palette／VRAM 與完整排版仍不由 record-level decode 推定 |
| `CONTROL-001` | 已命名的 record 周邊 opcode／expression 形狀 | `confirmed`（bounded） | 固定 csm3 `sub_080127E4` dispatch 與 handler callsite 證實 `0x0308`、`0x0309`、`0x030A`、`0x0001/2/3/6` 的 parser shape；每筆最多向後解析 8 個 command，未知 `0x0302/4/16/0x047e` 留 opaque | 追查未知 handler；不把 `0x0309`／`0x030A` 猜成換行／分頁 |
| `CONTROL-002` | PSI3 stream／record no-op round-trip | `confirmed`（decoded stream layer） | 13 resources、361 records、32092 stream bytes；source Shift-JIS re-encode `361/361`；original／encoded aggregate SHA-256 均為 `6fda79e61316e3e941e72bad156206bb855a352c546f95d3c1dba2a474025706`；opaque tokens `203`、rejected marker `1` | 仍未重建 LZ77 compressed bytes、resource pointer/span 或 ROM |
| `LENGTH-001` | record payload 修改長度契約 | `partial-confirmed` | 相同 byte length：record/decoded stream 層可原地保留 offset；zero padding：blocked，因 `0x0000` 是 terminator；變長：需 resource rebuild／後續 jump relocation，尚無 builder | 先以相同 byte length 做最小 translation batch；未知 padding／font width 維持 blocked |
| `RUNTIME-001` | mGBA boot snapshot 是否能直接證實文本渲染路徑 | `blocked` | 一次性 mGBA 0.10.5 GDB snapshot 讀到 `PC=0x03003652`、`DISPCNT=0x1140`、`BG0CNT=0x0088`、`KEYINPUT=0x03ff`；沒有文字 ROM-to-VRAM match | 不再嘗試 port shim；待有可重現 scripting/headless 路徑或明確 debug 入口再開 runtime |
| `RUNTIME-002` | mGBA scripting/headless 文本偵察 | `blocked` | 已安裝 CLI 不接受 `--script`；未保留未驗證的 GUI／GDB 實驗工具 | 先解決工具能力與可重現入口，否則維持靜態候選狀態 |
| `RUNTIME-003` | 共用 `core/gba` 標準 capture 是否能取得 B3CJ live RAM／VRAM／OAM | `blocked` | `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s core/gba/test -v` 的 6 項測試通過；B3CJ 自有 mGBA process 的 `-C ports.qt.gdbPort=25352` 未建立 listener，2345 已由其他 session 使用；一次重用 `/private/tmp` redirect dylib 也未建立 25351。沒有產生新的 raw dump | 待有不碰其他 session 的可用 GDB port 或明確 debug 入口，再用 `core/gba/capture_runtime.py`；不重寫遊戲專屬 client |
| `RUNTIME-004` | M2.3 以獨立高位 port 取得 live palette／writer／VRAM/OAM 證據 | `blocked` | 先以 bind preflight 證實 `24387` 空閒；只載入本作 POC ROM 的 PID `26484` 執行 `-g -C ports.qt.gdbPort=24387`，`lsof -p 26484` 證實實際 listener 是該 PID 的 `*:2345`，`24387` refused；透過自有 `2345` 執行 core capture，但 `qSupported:multiprocess+` retry 後 timeout。已停止 PID，兩 port 事後均無 listener，沒有 runtime summary／raw dump | 不再把 `ports.qt.gdbPort` 當 CLI port shim；待有可重現、互不干擾的 runtime 入口，才補 palette、writer destination、VRAM/OAM layout 與畫面 glyph 可讀性證據 |
| `FONT-001` | 字型 resource、cell 格式、code-unit lookup 與 bounded identity | `confirmed`（static） | 本機 type-3 id 2 `BIT` payload file `0x14d5c6c`、glyph base `0x14d5c88`、2144×24-byte cells；`sub_0800348C` function/literal hash、table A/B、fallback 與 `gUnk_03002984 + glyph_id*0x18` 公式均重跑吻合；8 個 source Shift-JIS identity/addressing samples 分開記錄 | 以 fail-closed allocation manifest 接到最小回插 slice；palette／VRAM 仍由 RUNTIME-003 獨立處理 |
| `FONT-002` | 實際 code format 的 physical slot 掃描 | `confirmed`（static） | 11280 formula candidates、6879 strict Shift-JIS pairs、2087 mapped physical slots；全零 physical cells 28，其中未引用安全空槽 `0x845..0x85f` 共 27；非空不可尋址槽 `0x141..0x15e` 共 30，未分配 | 只允許 27 個明確空槽；zero table fallback 與 out-of-resource target 維持 blocked |
| `FONT-003` | glyph cell encoder／靜態 POC | `confirmed`（static POC） | 既有 GNU Unifont 17.0.05、固定 SHA／授權；`ec48`／`ec49` → slots `0x845`／`0x846`，table/cell 修改區域 52 bytes、實際非零 byte diff 43，static render 含 adjacent untouched `0x844`；patched ROM／PGM hash 收據見 `research/m2.2-font.md` | 未更新 ROM checksum、script container 或 runtime QA；不能稱翻譯或發布 patch |
| `FONT-004` | fail-closed glyph allocation manifest／record encoder | `confirmed`（bounded static POC） | `research/m2.3-glyph-manifest.json` 固定 B3CJ／source／font hash 與唯一 `0x845..0x85f` 範圍；`tools/encode_m2_3_poc.py` 對 `ec48`／`ec49`、兩筆 4／2-byte record 重抽 mapping／cell、record／PSI3 stream 與原 resource span 內 LZ77；summary 收到 patched ROM SHA-256 `ce99a443cfab8f84cc7f7a0319b9271ce3173dc64c488ca138696ae938460a07`，所有差異均在 manifest regions；測試另拒絕 duplicate、strict collision、hash mismatch、fallback／out-of-resource 與 capacity overrun | 仍只證實 static POC；未知 VM／排版、palette／VRAM/OAM、pointer／header／BPS rebuild 與 runtime 可讀性不升格 |
| `SOURCE-001` | 可供帳本使用的 bounded 日文原文表 | `confirmed`（M1.5 範圍） | `tools/extract_static.py` 對固定 ROM 可重抽 361 筆 `string_id／locale／source_text／provenance`；ignored JSONL 不 stage，tracked 文件只留 hash／offset／control token | 完成 font／VM／回插契約後，才建立可翻譯的工作帳本；目前不宣稱全遊戲 source coverage |
| `TRANSLATION-001` | 劇情、支線、夥伴、鍛造、戰鬥、道具的有限量翻譯 | `blocked` | 雖已有 bounded 本機原文表與 M2.1 round-trip，但尚無完整 VM／字型／回插契約與可提交翻譯 ledger | 先選 1–2 筆、保持相同 Shift-JIS byte length、控制資料不變的短批次；本里程碑不宣稱已開始翻譯 |

## 第一個可重現檢查

對使用者提供的 ignored 日版 ROM 執行：

```sh
python3 games/summon-night-craft-sword-3/tools/inspect_rom.py --strict \
  games/summon-night-craft-sword-3/roms/base/B3CJ-jp-from-zip.gba
python3 games/summon-night-craft-sword-3/tools/scan_static.py \
  games/summon-night-craft-sword-3/roms/base/B3CJ-jp-from-zip.gba \
  --output games/summon-night-craft-sword-3/work/static-report.json
PYTHONDONTWRITEBYTECODE=1 python3 games/summon-night-craft-sword-3/tools/extract_static.py \
  games/summon-night-craft-sword-3/roms/base/B3CJ-jp-from-zip.gba \
  --output games/summon-night-craft-sword-3/research/summon-night-craft-sword-3-decoded.jsonl \
  --verify-roundtrip
PYTHONDONTWRITEBYTECODE=1 python3 games/summon-night-craft-sword-3/tools/inspect_font.py \
  games/summon-night-craft-sword-3/roms/base/B3CJ-jp-from-zip.gba \
  --source-jsonl games/summon-night-craft-sword-3/research/summon-night-craft-sword-3-decoded.jsonl \
  --summary-output games/summon-night-craft-sword-3/work/m2.2-font-summary.json
PYTHONDONTWRITEBYTECODE=1 python3 games/summon-night-craft-sword-3/tools/encode_m2_3_poc.py \
  games/summon-night-craft-sword-3/roms/base/B3CJ-jp-from-zip.gba \
  --source-jsonl games/summon-night-craft-sword-3/research/summon-night-craft-sword-3-decoded.jsonl \
  --manifest games/summon-night-craft-sword-3/research/m2.3-glyph-manifest.json \
  --font-source vendor/fonts/unifont/unifont-17.0.05.hex.gz \
  --output games/summon-night-craft-sword-3/work/m2.3-poc.gba \
  --summary-output games/summon-night-craft-sword-3/work/m2.3-poc-summary.json \
  --render-output games/summon-night-craft-sword-3/work/m2.3-poc.pgm
```

`--strict` 會把 game code、header checksum、size、CRC32 與公開 reference SHA-1 一起作門檻。這次本機 readback 的 SHA-256 是 `39bc4cf448106aa4b8cdde235632ffb57432c4b1919c8843510b70b3787fad2d`；若其他 clean dump 不同，先保留完整 hash 與差異，不修改 ROM 或用補丁檔冒充來源 ROM。`static-report.json` 是 ignored 產物，只提交工具與本帳本的摘要。

本次完整 ignored 靜態報告的 SHA-256 為 `cefdd9e0d8197b9642976ce976538a04d456d173d4837c02f6016a46a4ae0aed`；報告由上述 scanner 直接重建，不把報告或其中任何原始 bytes 加入 Git。

靜態掃描明確有界：Shift-JIS-shaped run 預設只掃 halfword alignment `0`、至少 8 個 units、最多保存 32 筆；LZ77／RLE 各最多嘗試 2048 個 header、展開上限 `0x40000`。因此「沒有候選」也不能視為全 ROM 證明；本次結果只足以把上述 offset 列為候選。

M2.1 extractor 的固定收據是 `records=361`、resource IDs `9,10,11,12,14,15,16,17,18,19,22,24,25`；ignored JSONL SHA-256 為 `a050790267679a35b1300f8ed3056271b6c481124790e9249484ce9d1d7966e3`。`--verify-roundtrip` 收到 `32092` decoded stream bytes、source re-encode `361/361`、opaque tokens `203`、rejected marker `1`，original／encoded aggregate SHA-256 同為 `6fda79e61316e3e941e72bad156206bb855a352c546f95d3c1dba2a474025706`。此輸出含日文 `source_text`，只可存在被 ignore 的 research 路徑，不得 stage；完整控制碼、opaque 與 length-contract 收據見 [`research/m2.1-control-roundtrip.md`](m2.1-control-roundtrip.md)。

M2.2 font inspector 的固定收據是 type-3 resource `id=2`、BIT glyph base
`0x14d5c88`、`slots=0x860`、`cell=0x18`、strict mapped physical slots `2087`、
safe blank unreferenced slots `27`（`0x845..0x85f`），以及 source corpus
`records=361`／`unique_double_byte_units=382`。它也會拒絕未吻合 B3CJ identity、
reviewed csm3 function hash 或 lookup literal 的輸入；完整 samples、POC 與未知項目見
[`research/m2.2-font.md`](m2.2-font.md)。

M2.3 encoder 的固定收據是 `allocations=2`、`records=2`、`changed_bytes=1753`、
resource compressed sizes `485/496` 與 `1652/1664`，font mapping／cell、record／
PSI3 stream 均 byte-identical；manifest／測試／runtime 收據見
[`research/m2.3-poc.md`](m2.3-poc.md)。

## 外部資料索引

- [Data Crystal 遊戲頁 oldid=69650](https://datacrystal.tcrf.net/wiki/Summon_Night_Craft_Sword_Monogatari%3A_Hajimari_no_Ishi?oldid=69650)：B3CJ、容量、CRC32 與 header checksum 的候選 metadata。
- [Data Crystal TBL oldid=53006](https://datacrystal.tcrf.net/wiki/Summon_Night_Craft_Sword_Monogatari%3A_Hajimari_no_Ishi/TBL?oldid=53006)：主日文字型的公開 code-table 線索；已與本機 bounded record 交叉驗證，但不是完整原文來源。
- [csm3 固定 commit](https://github.com/jiangzhengwenjz/csm3/commit/7e388ac861bbac289b1f86dc5b8fa46d47b1a1a2)：可供控制流／資料結構研究的公開工程參考；其 build/reference hash 與本機 ROM 分開記錄，固定 checkout 的 root license 狀態見 [`research/external-sources.md`](external-sources.md)。
- [臺灣繁體 Wikipedia 條目](https://zh.wikipedia.org/wiki/%E5%8F%AC%E5%96%9A%E5%A4%9C%E9%9F%BF%E6%9B%B2_%E9%91%84%E5%8A%8D%E7%89%A9%E8%AA%9E_%EF%BD%9E%E8%B5%B7%E6%BA%90%E4%B9%8B%E7%9F%B3%EF%BD%9E)：標題與部分角色名稱的既有中文寫法參考。
- [巴哈姆特流程攻略](https://forum.gamer.com.tw/G2.php?bsn=5499&lorder=1&parent=584&sn=578)：本作流程與專有名詞的社群用語交叉參考；不把攻略內容當成 ROM 原文。

既有英文／中文 patch 只可用來核對工程方向、已知版號或 bug 線索；不可把 patch 內的翻譯腳本直接當作日文來源，也不可把 ROM、完整原始腳本或未授權字型帶進 Git。
