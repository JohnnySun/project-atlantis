# 《召喚夜響曲 鑄劍物語 ～起源之石～》工作區

本目錄只處理日版 GBA 第三代《サモンナイト クラフトソード物語 〜はじまりの石〜》（候選 game code `B3CJ`）。不修改第一代或第二代，也不把 KONKR、Project Advance、ADB 或其他裝置部署問題帶入 Project Atlantis 核心架構。

本作採用 `.agents/skills/gba-localization/SKILL.md` 與 `docs/TRANSLATION-LEDGER.md` 的新遊戲帳本流程：日文原文只在本機 `research/*-decoded.jsonl`，翻譯編輯只在本機 `work/`，可提交資料只使用 `translations/*.jsonl` 的 `source_hash` 形式。ROM、patch、渲染圖、OCR 輸出與大段掃描結果不提交。

## 目前狀態

截至 2026-08-16，已從使用者提供的日版 ZIP 唯讀取出單一 32 MiB ROM，並以 `inspect_rom.py --strict` 證實為 `B3CJ`。M1.5、M2.1、M2.2、M2.3、M2.4、M2.5、M2.6、M2.7、M2.8、M3 ledger、M4.1、M4.2、M4.3、M4 target QA、M5.1 static pointer relocation POC 與 M5.2 resource-24 relocation static batch 已完成：依固定的 csm3 callsite 鎖定 type-2 script resource table，對 LZ77／`PSI3` 資源建立有界 extractor，從 13 個 resource ID 可重抽 361 筆真實日文 record；新增控制碼保真 parser、opaque fallback、Shift-JIS source re-encode 與解壓 stream byte-identical round-trip；再由 type-3 `BIT` resource、lookup table、24-byte glyph cell 與固定 codepage samples 建立可重跑的 static renderer、27-slot allocation manifest、fail-closed glyph encoder、五筆 cumulative zh-TW／7-glyph bounded static build、resource-24 relocation、BPS apply round-trip、target／adjacent static proof、target-side QA、單一 resource directory redirect、361 筆 pointer／record／layout contract audit，以及 source／work／ledger hash-guarded restore-strip validator。M2.7 transport 仍 blocked；完整 VM／未命名 opcode、line/page／glyph-width semantics、palette／runtime VRAM、自然畫面 QA、人工翻譯審核與全遊戲批次翻譯仍未完成；目前 target 仍是 `ai_draft`，不是可發布 patch。完整狀態見 [`research/recon-ledger.md`](research/recon-ledger.md)、[`research/m3-ledger.md`](research/m3-ledger.md)、[`research/m4.1-wood-chopping.md`](research/m4.1-wood-chopping.md)、[`research/m4.2-warning-label.md`](research/m4.2-warning-label.md)、[`research/m4.3-ellipsis-label.md`](research/m4.3-ellipsis-label.md)、[`research/m4-batch-qa.md`](research/m4-batch-qa.md)、[`research/m5.1-pointer-relocation.md`](research/m5.1-pointer-relocation.md)、[`research/m5.2-reward-relocation.md`](research/m5.2-reward-relocation.md)、[`research/static-format.md`](research/static-format.md)、[`research/m2.1-control-roundtrip.md`](research/m2.1-control-roundtrip.md)、[`research/m2.2-font.md`](research/m2.2-font.md)、[`research/m2.3-poc.md`](research/m2.3-poc.md)、[`research/m2.4-runtime.md`](research/m2.4-runtime.md)、[`research/m2.5-batch.md`](research/m2.5-batch.md)、[`research/m2.6-runtime.md`](research/m2.6-runtime.md)、[`research/m2.7-runtime.md`](research/m2.7-runtime.md)、[`research/m2.8-layout.md`](research/m2.8-layout.md) 與 [`ROADMAP.md`](ROADMAP.md)。

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

尚未由 extractor 覆蓋的候選仍必須再經反組譯、ROM-to-VRAM byte match 或 mGBA 執行期讀取確認。共用 `core/gba/capture_runtime.py` 與 renderer 已可用，且共用測試 6 項通過；M2.4 依其他成功 session 改用 `-C gdb.port=<high-port>`，兩輪 fresh process 分別使用 `24763`／`24764`，但第一輪 GUI process 未建立 listener，第二輪 headless binary 明確回報 `Debugger: Couldn't open socket`。兩次均以本作 diagnostic 收到 `ConnectionRefusedError`，程序已停止，沒有 `qSupported`、breakpoint/watchpoint、runtime summary、VRAM／palette／OAM 或畫面證據。這次收據記為 `RUNTIME-005`，只限制 live RAM／VRAM／palette／OAM 交叉驗證，不否定 M2.4 已由本機 function hash 收斂的 writer→RAM output-buffer static contract；不新增共用 GDB／dump／renderer。

## M2.2 字型鏈與 static POC

`tools/inspect_font.py` 只接受固定 B3CJ 身分，並逐次驗證 csm3 commit `7e388ac` 對應的本機 function ranges／literal pool。它確認 type-3 resource `id=2` 的 `BIT` payload 位於 file `0x14d5c6c`、glyph base `0x14d5c88`，共有 `0x860` 個 24-byte、12×12 cell；`sub_0800348C` 的 table A/B、zero fallback 與 `glyph_id=value-1` 定址也已由 8 個 identity/addressing samples 交叉驗證。掃描得到 2087 個 strict code units 對應 2087 個 physical slots，安全未引用空白槽是 `0x845..0x85f` 共 27 個；非空但不可尋址的 `0x141..0x15e` 共 30 個不分配。palette、VRAM/OAM arrangement 與 runtime 仍維持獨立 blocked。

只用 repository 已固定的 GNU Unifont 17.0.05 產生兩個 ignored static POC glyph：opaque `ec48`／`ec49` 分別暫映射到 `的`／`你` 的 `0x845`／`0x846`，並用 untouched `0x844` 做鄰接 render。POC 的 table/cell 修改區域共 52 bytes，固定 source 下實際非零 byte diff 為 43；輸出 ROM／PGM／summary 均在 ignored `work/`，不代表翻譯或可發布 patch。來源、SHA-256、授權及 16→12 packing 規則見 [`research/font-sources.md`](research/font-sources.md) 與 [`research/m2.2-font.md`](research/m2.2-font.md)。

重跑 font summary：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 games/summon-night-craft-sword-3/tools/inspect_font.py \
  games/summon-night-craft-sword-3/roms/base/B3CJ-jp-from-zip.gba \
  --source-jsonl games/summon-night-craft-sword-3/research/summon-night-craft-sword-3-decoded.jsonl \
  --summary-output games/summon-night-craft-sword-3/work/m2.2-font-summary.json
```

## M2.3 fail-closed glyph allocation／bounded POC

`research/m2.3-glyph-manifest.json` 固定 B3CJ、M2.1 source-table、GNU Unifont
source hash 與唯一可分配範圍 `0x845..0x85f`。`tools/encode_m2_3_poc.py` 只接受
這些固定輸入，保留既有 mapping，拒絕 source／ROM／font hash mismatch、strict
Shift-JIS collision、重複 code unit／slot、範圍外 slot、未分配 target、長度不符與
resource span capacity overrun；新的 opaque code unit 在 clean ROM 上只可使用
`table_value=0` 的未佔用 entry，patch 後必須重新 lookup 為 mapped，不能把
fallback 或 out-of-resource 當成可用目標。

本切片以 `ec48`／`ec49` 兩個 static POC glyph（暫用 `的`／`你`）及兩筆相同
byte length 的短 record 驗證：resource 22 的 `485/496` 與 resource 25 的
`1652/1664` compressed/span 均符合原容器；font mapping／cell、record、PSI3
stream 均 byte-identical round-trip，patched ROM／PGM／summary 全在 ignored
`work/`。測試也會拒絕重複、strict collision、hash mismatch、fallback／
out-of-resource 狀態與容量超限。完整 hash、stable ID 與 runtime 收據見
[`research/m2.3-poc.md`](research/m2.3-poc.md)。

重跑 M2.3 POC：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 games/summon-night-craft-sword-3/tools/encode_m2_3_poc.py \
  games/summon-night-craft-sword-3/roms/base/B3CJ-jp-from-zip.gba \
  --source-jsonl games/summon-night-craft-sword-3/research/summon-night-craft-sword-3-decoded.jsonl \
  --manifest games/summon-night-craft-sword-3/research/m2.3-glyph-manifest.json \
  --font-source vendor/fonts/unifont/unifont-17.0.05.hex.gz \
  --output games/summon-night-craft-sword-3/work/m2.3-poc.gba \
  --summary-output games/summon-night-craft-sword-3/work/m2.3-poc-summary.json \
  --render-output games/summon-night-craft-sword-3/work/m2.3-poc.pgm
```

這仍是 static POC，不是已審核翻譯、完整 ROM 回插、BPS 或可發布 patch；palette、
writer destination、VRAM/OAM layout 與畫面 glyph 可讀性仍因 `RUNTIME-004`／
`RUNTIME-005` blocked。

## M2.4 runtime handshake diagnostic／static writer destination

本切片先 review 其他已成功 session 的 `-C gdb.port=<high-port> -C skipBios=1 -g`
模式與單次 GDB client，再對 M2.3 POC 做最多兩輪 fresh process。第一輪
`24763` 的 homebrew mGBA process PID `29811` 命令列與 ROM ownership 對上，但
沒有 listener；第二輪使用其他 session 已成功的 headless mGBA 與 `24764`，直接
回報 `Debugger: Couldn't open socket`。兩輪 process 都已停止，diagnostic 對已
釋放的 ports 收到 `ConnectionRefusedError`，未取得 `qSupported` 或任何 runtime
breakpoint／watchpoint hit。完整 launcher、PID、port、client delay／ACK／retry 與
失敗邊界見 [`research/m2.4-runtime.md`](research/m2.4-runtime.md)。

本作新增 [`tools/runtime_m2_4.py`](tools/runtime_m2_4.py) 與測試。它不啟動或停止
mGBA，只對單一已核對 listener 使用共用 `core/gba/gdbstub_client.py`，並輸出不含
原文／raw memory 的 ignored diagnostic。若 listener 不可用，仍會驗證本機 B3CJ
writer ranges：`sub_080036F8 → sub_08002CB4` 的 `r1` output-buffer span／per-glyph
stride 是 `0x80`，`sub_0800379C → sub_080031E8` 是 `0x40`；兩條都先經
`sub_0800348C` lookup。這是 confirmed-static 的 RAM/output-buffer contract，
不是 VRAM address，也不證明自然 reachability、palette、tilemap、OAM 或畫面可讀性。
同一 diagnostic 重新驗證 changed `0x845/0x846` 與 adjacent untouched `0x844` 的
static 12×12／24-byte render。M2.4 runtime gate 仍 blocked，沒有準備 translation
ledger candidate。

## M2.5 首批 zh-TW ledger／static build

本切片從 ignored 的 361 筆 source table 選出 resource 24 的結構完整短內容群，先以四筆同長度候選做容量預檢；四筆同時重建會使 LZ77 輸出超過原 span，因此 fail closed，最後只提交一筆有界 record：`b3cj:t2:024:0x0064`。它保留 `0x0308`／`0x0000` control shape，payload 維持 14 bytes／7 cells／1 line，target 是臺灣繁體 AI 初稿 `這次的獎品是…`，沒有專有名詞，未把 M2.3 的 `ec48`／`ec49` static 假資料當翻譯。

`research/m2.5-batch-plan.json` 固定 source／ROM／font hash、source hash、target hash、code units、resource span、adjacent untouched IDs 與三個 fail-closed allocation：`ec64`→`0x847`（這）、`ec65`→`0x848`（獎）、`ec66`→`0x849`（是）。`build_m2_5_batch.py` 會先產生 ignored source adapter，再經 `restore_translations.rb`／`strip_translations.rb` 產生只含 hash、target、status／review metadata 的 tracked ledger；build 後重新抽取 361 筆，target 1、untouched 360，兩筆相鄰 record byte-identical，並由 core BPS create／apply 證實 applied ROM 與 target byte-identical。

固定收據、hash 與未證實邊界見 [`research/m2.5-batch.md`](research/m2.5-batch.md)；ROM、完整原文、working/source adapter、target ROM、BPS、raw dump 與圖片均留在 ignored `roms/`／`research/*-decoded.jsonl`／`work/`。runtime screen reachability、palette、VRAM／tilemap／OAM、畫面可讀性與翻譯審核仍 pending。

## M2.6 第一筆翻譯 runtime renderer QA

本切片先核對 M2.5 clean／target／BPS hash，再以 target ROM 做兩次 fresh mGBA launcher 嘗試，均使用本作專屬 port `25126`、`-C gdb.port=25126 -C skipBios=1 -g`、單一 connection policy 與 core GDB readiness。第一輪 `/opt/homebrew/bin/mgba` 的自有 PID `50537` 啟動後立即退出且沒有 listener；第二輪 `/private/tmp/atlantis-mgba-headless-build2/mgba-headless` 的自有 PID `50654` 輸出 `Debugger: Couldn't open socket`，事後 port 無 listener。兩個 PID 都已停止，沒有連線到其他 session，也沒有取得 `qSupported`、breakpoint／watchpoint 或 live memory。

`tools/runtime_m2_6.py` 會先 fail closed 驗證 base／target／BPS／applied hash、M2.5 target ID、三個 glyph mapping 與 `0x846` adjacent untouched cell，再用 `core/gba/gdbstub_client.py` 做一次 qSupported readiness；目前兩份 ignored diagnostic 都是 `handshake=blocked`，error 是本環境 socket connect 的 `PermissionError [Errno 1]`，不能把它解讀成 ROM 或譯文失敗。static target proof 確認 `ec64/ec65/ec66`→`0x847/0x848/0x849`、target render hash，以及 glyph `0x846` base／target cell／render hash 完全一致；M2.5 已重抽 361 筆（target 1／untouched 360）並完成 BPS byte-identical apply。

因此 M2.6 runtime gate 仍是 transport-only pending：沒有自然／受控 consumer coverage、font cache、writer destination、palette、VRAM／tilemap／OAM 或畫面可讀性證據，`ai_draft` 不變，也不擴大第二筆翻譯。下一個可執行 runtime 方案是使用 `/private/tmp` 的 compile-time GDB-port mGBA build，或在允許 localhost socket 的執行環境重跑同一個 hash-guarded diagnostic；不得把這兩輪 negative 升格為畫面失敗。

## M2.7 M2.5 target transport-only QA

本切片只重試既有 target `b3cj:t2:024:0x0064` 的 mGBA／GDB transport，不新增第二筆翻譯。先用 `lsof` 確認高位 port `25273`、`26371` 均無 listener，再分別以 `/private/tmp/atlantis-mgba-headless-build2/mgba-headless` 與另一個 `/private/tmp/mgba-smt2-sdl-build/sdl/mgba` 進行 fresh process 啟動；兩者都以 `-C gdb.port=<high-port> -C skipBios=1 -g` 指向 M2.5 target，均回報 `Debugger: Couldn't open socket`，事後 port 仍無 listener，且只停止本輪自己的 foreground process。PTY wrapper 未暴露 child OS PID，因此 M2.7 report 不虛構 PID。

`tools/runtime_m2_7.py` 重用 M2.6 hash/static guard 與 `core/gba/gdbstub_client.py`，每次只開一條 connection，先做 `qSupported`／`?` readiness，再按需交給共用 capture；兩份 ignored report 都是 `connect=false`、`qSupported=null`、`PermissionError [Errno 1] Operation not permitted`。因此沒有自然／受控 consumer hit、breakpoint／watchpoint、font cache、writer→VRAM、palette、tilemap／OAM 或畫面 render 結果；`0x847/0x848/0x849` 與 adjacent `0x846` 只保留 M2.6 static proof。完整 launcher／port／listener／error／重跑命令見 [`research/m2.7-runtime.md`](research/m2.7-runtime.md)。下一個可執行方案是允許 localhost socket 的環境，或 `/private/tmp` compile-time GDB-port mGBA build；本輪不再重複同一 bind 方法，`ai_draft` 與單筆翻譯範圍不變。

## M2.8 靜態 pointer／record／layout contract audit

`tools/audit_layout.py` 以固定 B3CJ SHA-256 先做 ROM identity guard，再重用既有
extractor 逐一驗證 13 個含文字 resource、361 筆 record 與 source Shift-JIS
re-encode。13 個 pointer entry 收斂為 11 個 payload groups；resource `9`／`10`
是 resource `11` 的 zero-span alias，所有 positive span 不重疊且 compressed size
不超過自身 span。record contract aggregate SHA-256 是
`9aebe71ca654f735b41c913c08b79875f04b9b164a9c024373389b53dd70191e`。

目前只確認一個 `0x0308` inline text segment 與 `0x0000` terminator、最大
36-byte／18-code-unit payload，以及已觀察 opcode／opaque 計數；line/page/wait、
glyph width、變長／padding、compressed container rebuild 與 runtime layout 都不
猜測。`tools/test_audit_layout.py` 覆蓋真 ROM contract、span overrun rejection 與
lossless Shift-JIS code-unit count；完整收據見
[`research/m2.8-layout.md`](research/m2.8-layout.md)。

## 文字系統研究邊界

外部 [Data Crystal TBL](https://datacrystal.tcrf.net/wiki/Summon_Night_Craft_Sword_Monogatari%3A_Hajimari_no_Ishi/TBL?oldid=53006) 提供主日文字型的 16-bit code-table 線索；本輪已用固定 B3CJ ROM 的多個 `0x0308 ... 0x0000` record 交叉驗證：VM halfword 仍按 little-endian 讀取，但 marker 後的 codepage bytes 必須以記憶體原始順序直接做 strict Shift-JIS decode，不能逐 halfword swap。M2.1 另以 csm3 handler／expression callsite 證實有限控制形狀，未知 word 保留 opaque；這不代表字型與所有 opcode 都已命名，也不能假設第一、二代的格式相同。完整格式見 [`research/static-format.md`](research/static-format.md) 與 [`research/m2.1-control-roundtrip.md`](research/m2.1-control-roundtrip.md)。M2.5 另以固定 plan、source hash、code-unit／glyph allocation、resource span 與重抽取收據限制第一筆翻譯，不把 static build 當成 runtime QA。研究時必須分開記錄：

1. 字串在哪裡、如何分界、是否有指標、壓縮與控制碼如何運作。
2. glyph 的位址／tile 定址是否已找到。
3. 每個 glyph 的 Unicode 身分是否有獨立交叉證據。

目前已建立受限的 `research/summon-night-craft-sword-3-decoded.jsonl` 作為本機原文邊界；OCR 只能作候選證據，不能直接複製到翻譯記錄。已命名控制碼可做 record/stream round-trip；M2.5 僅建立一筆 AI 初稿 static batch，未知 opcode、完整排版、runtime 畫面與人工審核仍未完成，不開始劇情、支線、夥伴、鍛造、戰鬥或道具的大批翻譯。

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

## 完成標準（M5.2 static slice 已達成，畫面 QA／翻譯審核尚未達成）

- clean 日版 ROM 的 header、revision、CRC32、SHA-256 已記錄並可重跑。
- type-2 script table、LZ77、`PSI3` stream、bounded text record、Shift-JIS codepage 與 csm3 consumer 有遊戲專用、可重跑證據。
- 已命名控制碼的參數寬度、opaque fallback、361 筆 source re-encode 與 13 個 resource 的 decoded stream byte-identical round-trip 有收據。
- M2.2 已由本機 callsite／literal、type-3 BIT resource、code-unit lookup、12×12／24-byte cell 與 8 個 identity/addressing samples 證實 static glyph chain；已掃描 2144 slots，保留 27 個明確空槽，並完成不破壞既有 mapping 的 2-glyph static POC。
- M2.3 已固定只允許 `0x845..0x85f` 的 glyph allocation manifest；2 個 opaque POC code unit、2 筆等長短 record 通過 source／ROM／font hash、font mapping／cell、record／PSI3 stream 與原 resource span capacity 的 fail-closed byte-level round-trip。這不等於翻譯或完整 ROM 回插。
- M2.5 已以 `restore → work → strip` 建立 1 筆 `ai_draft` zh-TW ledger；固定 `source_hash`、14-byte／7-cell contract、`ec64/ec65/ec66`→`0x847/0x848/0x849` allocation、resource 24 span 與兩筆 adjacent untouched record。
- M2.5 static build 重新抽取全部 361 筆 record，驗證 target 1／untouched 360、其他 resource decoded bytes 不變；原 resource span 為 `1379/1392`，新輸出 `1392/1392`，BPS 生成／套用後 target ROM byte-identical。這仍不是發布 patch 或畫面通過。
- M2.6 以 target ROM 完成 base／target／BPS hash guard、三個 changed glyph 的 static target render 與 adjacent glyph `0x846` base／target byte-identical proof；兩輪 fresh launcher 的 port／log／handshake negative 都只記為 transport pending，沒有 live renderer coverage。
- M2.7 再以 `25273`／`26371` 與兩個不同 mGBA binary 做 fresh listener retry；兩輪均無 listener，single-connection probe 在 `connect()` 前收到 `PermissionError`，沒有 qSupported／consumer／VRAM evidence。此為 transport-only blocker，不是 ROM／譯文失敗。
- M2.8 以固定 ROM hash 重抽 13 個 resource／361 筆 record，確認 11 個 pointer payload groups、resource `9`／`10` 的 zero-span alias、positive span 不重疊、361/361 source re-encode 與 record-contract aggregate SHA-256；line/page/wait、glyph width 與完整 container rebuild 仍 unknown。
- M3 ledger validator 以固定 source-table SHA-256 `a050790267679a35b1300f8ed3056271b6c481124790e9249484ce9d1d7966e3` 重驗 361 筆 local source、1 筆 tracked ledger、stable string ID、`zh-TW`／`ai_draft` 與 core restore→strip JSON-value round-trip；source key 與 hash drift 負面測試通過。
- M4.1 以 resource 22 的一筆無 opaque 12-byte label 建立第二筆 cumulative `ai_draft` target；`ec67/ec6c`→`0x84a/0x84b`，existing mappings preserved，361 筆重抽為 target `2`／untouched `359`，resource 22 `493/496`，BPS 2117 bytes apply byte-identical。這仍不是人工審核、runtime QA 或發布 patch。
- M4.2 以 resource 16 的一筆無 opaque 10-byte warning label 建立第三筆 cumulative `ai_draft` target；existing mappings `8c78/8d90/8149/8140` preserved，無新 glyph allocation，361 筆重抽為 target `3`／untouched `358`，resource 16 `180/192`，BPS 2225 bytes apply byte-identical；resource-22 下一候選 `500/496` 已由 capacity guard 拒絕。這仍不是人工審核、runtime QA 或發布 patch。
- M4.3 以 resource 25 的一筆無 opaque 8-byte ellipsis label 建立第四筆 cumulative `ai_draft` target；`ec6d`→`0x84c`、existing `8163/8140` preserved，361 筆重抽為 target `4`／untouched `357`，resource 25 `1655/1664`，BPS 3301 bytes apply byte-identical。這仍不是人工審核、runtime QA 或發布 patch。
- `tools/audit_translation_batches.py` 已對四筆 bounded ledger 做 target-side QA：stable ID、target hash、code unit／byte length、單行寬度、controls、allowed allocation、已知簡體字漏入與 source-bearing ledger negative test 均通過；完整 source hash／restore-strip 仍由 `tools/validate_ledger.py` 驗證。
- M5.1 static pointer relocation POC 已將 resource 24 directory entry 從原 span 重導至 `0x1fbb1fc` zero-filled destination，361 筆 stable records／stream aggregate byte-identical；這只解除下一個 static capacity-expansion slice 的 pointer contract 風險，不代表完整 ROM 回插或 runtime 通過。
- M5.2 已以 `b3cj:t2:024:0x0078` 建立第五筆 `ai_draft` target，沿用 `ec65→0x848`、新增 `ec6e→0x84d`；resource 24 從 `0x17231fc`／`1392` bytes 重導至 `0x1fbb1fc`／`1536` bytes，361 筆 re-extract 為 target `5`／untouched `356`，BPS `4814` bytes apply byte-identical，target ROM SHA-256 `da3b83b5470f278f455672021e2ae87452bc92d93fdbf1126c0e994dde757cb1`、CRC32 `c81e7eb5`。這仍是 static-only，沒有 runtime／人工 review 或發布資格。
- M5.2 以 resource 24 的 `b3cj:t2:024:0x0078` 建立第五筆 cumulative `ai_draft` target `特獎　重金礦`；沿用 `ec65→0x848`，新增 `ec6e→0x84d`，resource compressed `1396` 移至 `0x1fbb1fc` 的 `1536`-byte span，361 筆重抽為 target `5`／untouched `356`，BPS `4814` bytes apply byte-identical。這仍是 static-only，不是人工審核、runtime QA 或發布 patch。
- 相同 byte length 的 record-level 原地修改可行；zero padding 縮短 blocked，變長需 resource rebuild；完整 VM、字型、LZ77／pointer encoder 與 ROM 回插仍待建立。
- 至少五個有限量 target 通過各自的 `restore → work → strip`／source hash contract 與 repository safety check；M3 validator 已重驗 source／work／ledger 分界，但五筆 target 仍需人工／術語／runtime review。
- 編碼器／回插器拒絕來源 hash、缺字、控制碼或長度不一致，而不是放寬檢查。
- 重建 ROM 重新抽取吻合；BPS round-trip 與 mGBA 核心畫面回歸另有收據。

目前已完成 clean 日版 ROM 身分／hash、M1.5 靜態 decoder、M2.1 控制碼保真 parser、361 筆 ignored source extraction、M2.2 static font chain／POC、M2.3 fail-closed allocation／bounded POC、M2.5／M4.1／M4.2／M4.3／M5.2 cumulative `ai_draft` zh-TW static build／BPS round-trip、M2.8 pointer／record contract audit、M3 ledger restore-strip validator，以及 M2.6 target／adjacent static proof、M2.7 transport retry／diagnostic；尚無翻譯人工審核、完整 VM／multi-resource rebuild、自然畫面 runtime QA 或可發布 patch 收據。
