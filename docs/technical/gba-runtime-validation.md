# GBA ROM runtime／文字／選單 QA 技術決策

狀態：framework、無版權 fixture 與兩款 ignored ROM 的 framework-native smoke 已驗證；
copyright-safe receipt 見 `docs/evidence/gba-runtime-validation-smokes-20260816.md`。

## 問題與決策

Project Atlantis 需要在不逐款完整通關、也不把 ROM／save state／原文放進 Git 的前提下，
自動判定翻譯後的 record、pointer、glyph 與畫面是否仍然安全。單做 static scan 看不到實際
consumer 與渲染結果；單看 screenshot 或 OCR 又無法證明資料來源、相鄰 record 未受污染、
或畫面是否由預期文字 pipeline 產生。

第一版採用五層閉環：

1. strict case manifest 固定 ROM 身分、允許變更範圍、case reachability 與 assertion；
2. static preflight 驗 pointer／range／record／control／encoding／glyph width／layout／alias／adjacent；
3. 單一擁有的 mGBA process 與單一 GDB connection 取得 register、memory、break/watchpoint；
4. KEYINPUT consumer hook、受控 register/RAM/PC injection 或 launch-time savestate 抵達 case；
5. memory hash、VRAM/OAM/palette/tilemap render receipt 與 assertion 合併成 machine-readable report。

任何要求的能力、證據或判定條件缺失，結果都是 `unknown`，CLI exit code 為 2。它不會降級成
pass，也不會因畫面「看起來正常」而放行。

## 來源與可重用基礎

本框架直接重用：

- `core/gba/gdbstub_client.py`：GDB remote packet、register/memory、break/watchpoint、continue；
- `core/gba/capture_runtime.py`：標準 I/O 與記憶體區域 receipt 形狀；
- `core/gba/render_vram.py`：regular BG、tile grid、Mode 3；
- `core/gba/render_oam.py`：依 OAM placement 合成 OBJ；
- `core/ledger/`：原文只留 ignored local source/work、提交檔只含 hash 的邊界；
- `core/patches/bps_create.rb`／`bps_apply.rb`：BPS round-trip；
- 各遊戲既有 runtime probes：KEYINPUT read watchpoint、consumer argument hijack、
  ROM→RAM→VRAM/tilemap receipt 與 natural／controlled 分欄。

遊戲固定 offset、ROM revision、文字格式與 codepage 不進 `core/` 或 Skill；它們由各遊戲的
ignored case manifest 或遊戲文件負責。

## 官方能力基線與本機邊界

既有遊戲 probe 曾以 Homebrew mGBA 0.10.5 實測；本框架最終 smoke 使用上游 source commit
`afd6f14eaf8bd35214ed3fb9dc69a92bfc3877a9` 的 headless build，僅將 GDB listener 固定為
loopback high port。官方資料支持下列能力：

- mGBA 官方 README 列出 CLI debugger 與 GDB remote support；
- `doc/mgba-qt.6` 定義 `-g`（預設 2345）與 `-t/--savestate` launch-time state load；
- 官方 scripting API（0.10 起）有 `setKeys`、`runFrame`、memory/register read/write、
  `loadStateFile`／`saveStateFile`；
- mGBA `src/debugger/gdb-stub.c` 實作 GDB memory/register read/write、step/continue 與
  breakpoint/watchpoint packets；
- mGBA 維護的 GBATEK fork 定義 GBA EWRAM/IWRAM/MMIO/palette/VRAM/OAM/ROM map、
  `KEYINPUT` 與 display/tilemap 語義。

參考：

- <https://github.com/mgba-emu/mgba>
- <https://github.com/mgba-emu/mgba/blob/master/doc/mgba-qt.6>
- <https://mgba.io/docs/scripting.html>
- <https://github.com/mgba-emu/mgba/blob/master/src/debugger/gdb-stub.c>
- <https://mgba-emu.github.io/gbatek/>

本機確認與限制要分開寫：

- 已確認：0.10.5 GDB memory/register、`Z/z` point、KEYINPUT read hook 與共用 renderer
  已被多款本機 probe 使用；新 framework 的 protocol unit tests 已通過。
- 已確認：同一 process 斷線後重連不可靠；framework 只對「初次 listener 尚未 ready」做
  bounded retry，連線建立後絕不自動接到另一個 process。
- 已確認：共享主機同時有多個 emulator；port 與 PID 所有權是 capability gate，不是便利資訊。
- 已確認：bind-probe 與 emulator bind 之間存在競態；runner 前必須再驗 listener PID 等於
  本次 `$!`，並把當下 PID／PPID／start time／command 與 launch 後保存的 initial token
  完整比對。只驗「port 剛才是空的」、numeric PID、ROM token 或 listener 不足以防止
  PID reuse／替代行程；identity 變更必須在 runner 連線前回傳 unknown。
- 有限原型：launch-time `-t` 是官方 CLI 能力，但第一版 attach runner 不自行建立或提交
  savestate；若使用，launcher 必須留下 state hash／ROM hash／命令 receipt。
- 未證實：0.10.5 的一般 CLI `-g` 是否能透過任意 `-C` key 改 port。現有 source 顯示一般
  debugger module 會在建立時直接 listen 固定位址；不可假設 config override 有效。
- 未證實：mGBA 0.11 future headless／startup scripting 行為不作為 0.10.5 驗收依據。

## Manifest 與 CLI

Schema：`schemas/gba-runtime-case.schema.json`。

入口：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 scripts/gba-runtime-qa.py validate-manifest CASE.json

PYTHONDONTWRITEBYTECODE=1 python3 scripts/gba-runtime-qa.py static CASE.json \
  --base-rom games/<game>/roms/base/base.gba \
  --candidate-rom games/<game>/work/candidate.gba \
  --output games/<game>/work/qa/static-report.json

PYTHONDONTWRITEBYTECODE=1 python3 scripts/gba-runtime-qa.py runtime CASE.json \
  --rom games/<game>/work/candidate.gba \
  --savestate games/<game>/work/local-state.ss0 \
  --port PORT \
  --output games/<game>/work/qa/runtime-report.json
```

Exit code：`0=pass`、`1=fail`、`2=unknown/config/capability`。

Runtime 指令不負責猜測或殺除既有 emulator。先由外層 session 啟動一個自己擁有的 PID，
確認專用 local port，再交給 runner；結束時只回收該 PID。`--rom` 在任何 GDB 連線前檢查
SHA-256/size，避免把正確 manifest 跑到錯誤 process/ROM。
`--savestate` 只在 manifest 宣告 `runtime.savestate` 時使用：runner 先驗本機檔案 hash/size，
連線後再驗至少一個 state-specific live memory predicate；兩者都成立才 exercise
`savestate-load-at-launch`。runner 不解析或輸出 state payload，也不把檔案加入 Git。

## Static 判定

### ROM 與 relocation

- base ROM SHA-256、size、GBA header game code 必須符合；
- candidate 所有 changed bytes 必須落在 `allowed_changed_ranges`；
- size change 未明確允許即 fail；
- target region 可要求 changed，before/after adjacent region 可要求 unchanged；
- `role=target|adjacent` 讓兩者成為 machine-readable contract；一旦宣告其中一種，strict
  loader 要求另一種也存在，不能只靠 region ID 名稱推測；
- pointer 讀取目前支援 GBA 32-bit little-endian，檢查 target range 與 alignment；
- `expected_target` 可再鎖 exact relocation，避免錯誤 pointer 因仍落在寬鬆 range 而通過；
- 兩個 pointer 意外指向同址是 unexpected alias；宣告同一 `alias_group` 卻分裂也是 fail。

### Record、encoding、control 與 layout

- terminator 必須在 allocated range 內，scanner 會跳過已宣告的 control arguments，避免把
  argument 中恰好等於 terminator 的值誤判成 record 結尾；
- `control_codes[].argument_units` 與 optional `argument_values` 驗 control introducer 的參數數量和值域；
- token 必須落在 allowed values、control 或 newline 集合；
- `preserve_controls` 比較 base/candidate control sequence，不只比較數量；
- glyph width 沒有個別值且沒有 default 時為 `unknown`；
- line width 或 line count 超限為 fail，對應預測 overflow/clipping；
- runtime render 的 `clip_guard` 可再對指定 rectangle border 做 machine check，
  `border_non_background_pixels=0` 才代表內容未碰到宣告邊界。

`max_width` 必須來自該遊戲實際 renderer/window，不可用通用 GBA 240px 當作文字框寬度。

## Runtime action 與證據強度

支援 action：

- `wait_until`：bounded memory condition；
- `run`：bounded free-run 後 interrupt；
- `keys`：KEYINPUT read watchpoint，在遊戲已讀取 hardware value 的 destination register
  寫入 active-low keys；直接寫 `0x04000130` 不可靠，因此不提供；
- `capture`：register、I/O、任意 bounded region hash、BG/OAM/Mode 3 render hash；
- `breakpoint`／`watchpoint`：stop packet、PC/LR/register receipt；breakpoint 可依 register
  對 consumer source/destination 做 bounded hash capture；breakpoint 只有 normalized PC 等於
  requested address 才算 exercised，watchpoint 也必須命中 requested address range；
- `step`：越過會重複觸發的 breakpoint instruction；
- `write_register`／`write_memory`：必須 `controlled=true`；memory 另須完整落在
  `controlled_write_ranges`，並做 before/after/readback hash。

State-assisted case 另以 `runtime.savestate` pin SHA-256/size 與 `state_predicates`。外層仍需
用該檔啟動自有 emulator PID；runner 證明「指定 state 檔 identity + 目前 live state」一致，
不把單純存在一個 state 檔誤當成已載入證據。

證據層級：

1. natural：遊戲由正常 boot/state/input 自己選到 case；
2. state-assisted：由合法本機 save/save-state 抵達，必須記錄 state hash 與來源；
3. controlled consumer：在已證實 consumer entry 覆寫 argument/RAM/PC 觸發指定 record；
4. static-only：未進入 runtime pipeline。

低層級不能冒充高層級。controlled consumer 可以證明「這個 record 經這條 pipeline 可讀、
可渲染」，不能證明自然遊戲流程會選到它。每份 report 仍需保留 natural reachability 結論。

## Render evidence

每個 capture 先讀 `DISPCNT`／`BGxCNT` 再解碼：

- regular BG：由 BGxCNT 算 charblock、screenblock、4/8bpp；
- Mode 3：240×160 BGR15 framebuffer；
- OBJ：由 DISPCNT bit 6 選 1D/2D mapping，使用 OBJ palette 後半 512 bytes，依 OAM
  position/size/tile/flip/priority 合成；
- receipt 只保存 SHA-256、尺寸、非零計數、BG/OAM metadata 與 clipping guard；raw
  VRAM/OAM/palette、render image 留在 `/private/tmp` 或 `games/<game>/work/`。

OCR 最多是額外交叉證據。沒有 pointer/consumer/memory/render receipt 時，OCR 或人工截圖
不能單獨讓 case pass。

## 與 re-extract／ledger／BPS 的閉環

Runtime framework 不取代遊戲 decoder/builder：

1. builder 先做 source hash、control、glyph 與 range gate；
2. rebuilt ROM re-extract 與 ledger/source table 對照；
3. static case 驗 target + adjacent、pointer/alias、layout；
4. BPS create→apply→byte compare；
5. runtime case 驗 consumer、RAM/VRAM/tilemap/render；
6. machine report 只留 hashes/metadata，原文、ROM、patch、state、raw dump 不提交。

對 OCR 型 extractor，不能做嚴格 byte-to-text round-trip 時，至少要求 static re-render +
live renderer + adjacent unchanged，並把 glyph identity confidence 分層保留。

## Capability diagnostics

Report 同時列 `required`、`exercised`、`unproven`：

- `register-read`／`memory-read` 在 connection probe 實際執行；
- input hook 才能證明 register-write + watchpoint + keyinput hook；
- breakpoint/watchpoint action hit 才算 exercised；
- BG/OAM/Mode 3 實際 render 才算相應 capability；
- memory write 要有 allowlist、write、readback；
- savestate 要同時通過本機檔 identity 與 live predicates；缺 `--savestate`、hash mismatch
  或 predicate mismatch 分別產生 unknown/fail diagnostics，不會冒充 exercised。

Listener connection refused、stub startup race、point packet 不支援、timeout、render 參數無法
判定、glyph width 未知，都有獨立 diagnostics；它們不是 assertion fail，也不是 pass。

## 無版權 fixture 與測試

`examples/gba-runtime-validation/build_fixture.py` 生成 576-byte 原創 blob，不可 boot，專測
static contract。負例：

- `adjacent`：相鄰 record 污染 + range 外變更；
- `pointer`：target range 錯；
- `unterminated`：allocated range 內無 terminator；
- `control`：control sequence 漂移；
- `control-arity`：control introducer 在 terminator 前缺少宣告的 argument unit；
- `encoding`：record 含 allowed/control/newline 以外的 unit；
- `overflow`：line width 超限；
- `unknown-width`：缺 glyph width，預期 exit 2；
- `alias`：未宣告的 pointer alias。

測試：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s core/gba/test -v
```

## 後續驗收 Session：短流程

1. `git status --short`，確認只寫本框架 owned paths；
2. 選兩款結構不同、已 ignored 的 ROM，記錄 SHA-256/size/game code，不提交 ROM；
3. 為每款建立 ignored `work/runtime-qa/<case>.json`；
4. 先跑 `validate-manifest` 與 static；
5. 為每款啟動 fresh、自有 PID、不同 port 的 mGBA，確認 listener/ROM ownership；
6. 跑 runtime，至少一款走 normal boot + KEYINPUT hook 到 menu/text consumer，另一款至少
   證明 boot/input 與不同 render/text pipeline；
7. 對 case 收 target + adjacent、consumer register-memory、VRAM/OAM/tilemap/render receipts；
8. 逐一確認 `required == exercised`、`status=pass`；任何 unknown 不准手動改 pass；
9. 把去除 raw data 的 smoke summary 寫入 `docs/evidence/`，raw report 留 ignored work；
10. 跑全測試、安全檢查、`git diff --check`，以 `git commit --only` 提交 owned paths。

## 證據邊界

- mGBA state payload 格式解析與 emulator process launch 仍由外層負責；framework 驗證檔案
  identity 與載入後 live predicates，不聲稱能由 state 檔本身推導全部遊戲狀態；
- 任意遊戲的自動 case discovery；manifest 仍需遊戲專屬逆向資料；
- 全遊戲所有 menu/text 的 coverage；case pass 只代表 manifest 指定範圍。
