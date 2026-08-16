# 《世界傳說：換裝迷宮 3》漢化工作區

本目錄只處理日版 GBA《Tales of the World: Narikiri Dungeon 3》（B3TJ）的
zh-TW 研究與本地化。ROM、存檔、完整日文原文表、解碼輸出與實驗產物都留在
本機，不進 Git；可提交的是偵察結論、可重跑工具、測試與不含原文的工作文件。

## 目前狀態

目前完成 M0 身分鎖定、M1 工程可行性偵察、M1.5 至 M1.8 的 bounded runtime 回合：已
確認一批以 NUL 結尾的標準 Shift-JIS 候選資料、可重現的嚴格抽取邊界、五窗
absolute／relative 指標分層，以及遊戲啟動期實際執行的 BIOS 圖形解壓縮路徑。
M1.5 已確認早期 KEYINPUT polling caller，但選定 record 的 read watchpoint 在
bounded menu 序列中為 negative。M1.6 已確認 `0x08003444` 會被真實 UI／資源
載入路徑呼叫，但本回合的 8 個 resolved pointers 全部在五個文字窗外；selected
record `0x08146EE0` read watchpoint 仍為 negative。M1.7 已確認 boot→state 4 的
dispatcher、`0x08009C68 → 0x0800A58C → 0x0800A388` setup caller，以及正常 A 鍵
edge 的 static 條件。M1.8 已以正常 START gate 重現
`A1AC → r1=A(OK) → edge bit0 → object +0x54 → A2C0(r0=1) → 0x08005E12`，
並觀察到 state 4→7 的 return 與固定畫面 hash；隨後 clean
`--trace-first-record` 的 4 個 resolver hits 仍全部在五窗外，strict source read
為 0。已建立不含原文的 8,938 筆 source-hash ledger scaffold，但其 decoder、
控制標記與 renderer 仍屬靜態候選。**尚未開始翻譯，也尚未證明文字 renderer、
字型 codepage 或可逆回插。**
不把既有英文 patch 的少量選單／開頭
內容當作完整翻譯來源。

M2 另完成一個明確分級的 live edge：以本作 `navigation_harness.lua` 進入 state 7
後，在第二次 `0x080025CC` parser entry 對 strict `sjis:0x140D68` 做一次已獲
`OK` ACK 的 `r1` injection，確認 source read `0x080027F4`、RAM output
`0x03001468`、formatter `0x080014F4`、glyph asset `0x081670C4` 與固定
transform store `0x080011F6 → 0x030007A0`。這是 **argument-injected** pipeline
proof；自然流程的 `0x081489EC` 仍是 nonstrict short span，selected
`sjis:0x146EE0` 仍未自然命中。詳見
[`research/m2-live-consumer-glyph-20260816.md`](research/m2-live-consumer-glyph-20260816.md)。

可重跑命令（mGBA listener 的 PID／port 必須由本 session 自己擁有）：

```sh
SDL_AUDIODRIVER=dummy mgba-headless -l 0 -g \
  --script games/tales-of-the-world-narikiri-dungeon-3/tools/navigation_harness.lua \
  games/tales-of-the-world-narikiri-dungeon-3/roms/base/Tales_of_the_World_Narikiri_Dungeon_3_JP_AGB-B3TJ-JPN.gba
PYTHONDONTWRITEBYTECODE=1 python3 \
  games/tales-of-the-world-narikiri-dungeon-3/tools/live_consumer_probe.py \
  games/tales-of-the-world-narikiri-dungeon-3/roms/base/Tales_of_the_World_Narikiri_Dungeon_3_JP_AGB-B3TJ-JPN.gba \
  --port 39123 --output /private/tmp/b3tj-live-consumer.json
```

probe 終止後須停止同一個自有 mGBA PID，再重新建立下一條 session；工具刻意採
connection-close-only，避免 mGBA breakpoint list cleanup hang 被誤判成遊戲結果。

後續的 state7 readiness receipt 見
[`research/m2-state7-readiness-runtime-20260816.md`](research/m2-state7-readiness-runtime-20260816.md)。
它在正常 state 4→7 return 後確認 `0x080A85D8 → 0x080A82AC` 及
`r0+0x28=0`，但 `none:256` 內 parser、strict source、output 與 IWRAM writer
皆為 0；這是 loader/readiness boundary negative，不是文字不存在的結論。

## ROM 身分

| 欄位 | 已核對值 |
| --- | --- |
| 標頭 title | `TOWNARIKIRI3` |
| game code / maker | `B3TJ` / `AF` |
| revision | `00` |
| 大小 | 16,777,216 bytes（128 Mbit） |
| CRC32 | `1867CCEF` |
| MD5 | `289bbb2e151a6ca11f896ca4712c9835` |
| SHA-1 | `263b5ba40b1e0afbc2c23f478cc83f794846a47f` |
| SHA-256 | `d083d66b818b1353a449af7f1dd4232b490c254a4107951a3749973d03a0a394` |
| GBA header complement | 實際 `0x31`、計算 `0x31`，通過 |

本機標頭、大小與 CRC 由 `tools/recon_rom.py` 核對；公開資料也交叉符合
GameHacking 的 AGB-B3TJ-JPN／CRC32 紀錄、Planet Emulation 的同 CRC ROM 條目，
以及 Suruga-ya 的日本版 AGB-P-B3TJ 商品資料：

- [GameHacking：Tales of the World: Narikiri Dungeon 3](https://gamehacking.org/game/6219)
- [Planet Emulation：日本版 ROM](https://www.planetemu.net/rom/nintendo-game-boy-advance/tales-of-the-world-narikiri-dungeon-3-japan)
- [Suruga-ya：AGB-P-B3TJ](https://www.suruga-ya.jp/product/detail/275000741)

## 已確認的工程證據

- 在五個明確資料窗執行嚴格 NUL／Shift-JIS 抽取，共產生 8,938 筆本機候選：
  `0x100000–0x103000`、`0x105000–0x10D400`、`0x111000–0x114000`、
  `0x140000–0x1C4000`、`0x1C8000–0x1CC000`。抽取器拒絕非法位元組、未終止
  記錄與 ASCII-only 假陽性，低控制位元組保留成 `{HH}`。
- `0x140000–0x1C4000` 是目前最強的事件／對話候選池：存在密集 NUL 字串、
  LF `0x0A`、格式 token（例如 `%s`、`%0t`、`%0g`、`%h`、`%k`、`%l`、`%d`）
  與大量對齊的 GBA 絕對指標交叉訊號。
- 以 `0x0EC69A0` 為起點的候選指標序列有 1,002 個非遞減 word，目標檔案偏移
  約 `0x1489D8–0x1BE194`。它很可能是資源／指令相關表，但尚未證明每個
  target 都是可直接替換的文字指標。
- 一個有界 mGBA runtime 回合在 `0x080DD440`、`0x080DD444`、`0x080DD44C`、
  `0x080DD450` 設 breakpoint，實際捕捉到 LZ77-VRAM 與 RLE-VRAM 呼叫；VRAM
  寫入 watchpoint 也捕捉到解壓後資料寫入 `0x06000000`。這證明 runtime 有
  執行中的圖形解壓縮，不證明這些資源是文字或字型。

完整證據、14 次呼叫摘要與限制見
[`research/recon-20260816.md`](research/recon-20260816.md)。

M1.5 的 pointer classification、選定 record、KEYINPUT／record watchpoint 與
ROM→VRAM exact-match 限制見
[`research/m15-consumer-20260816.md`](research/m15-consumer-20260816.md)。可重跑
工具是 [`tools/classify_pointers.py`](tools/classify_pointers.py) 與
[`tools/consumer_probe.py`](tools/consumer_probe.py)；兩者都只輸出 offset、
register、hash 與計數 metadata，不輸出完整日文原文。M1.6 的 resolver entry／
return、caller LR、五窗 filter 與 selected-record negative 見
[`research/m16-resolver-20260816.md`](research/m16-resolver-20260816.md)。

## 尚未確認與回插邊界

以下項目在沒有新的 renderer／runtime 證據前不可當作翻譯基礎：

- 標準 Shift-JIS 是靜態解碼工作假設；字元代碼到 GBA glyph 的實際映射、字型
  載入點、glyph 寬度與文字 VRAM 路徑尚未定位。
- `0x12` 等控制碼、換行與 `%` token 的參數語義尚未解出；任何翻譯記錄必須
  原樣保存控制碼，不能把它們當普通文字刪除或重排。
- 指標表、字串長度／容量、壓縮資源是否與文字池相連尚未證明。
- 尚無可處理變長／指標更新的 builder、容量檢查、checksum policy 或實機／mGBA
  回插驗證；目前不可宣稱能安全擴長字串。已存在的等長 round-trip POC 只接受
  exact strict record 與不變的控制／換行形狀，不能替代完整 builder。
- 本次只完成有限 runtime 證據；M1.8 已可靠導航離開 state 4，但 state 7 的
  特定 menu/event 文字畫面仍未以 source consumer 證明。M1.8 的
  `--trace-first-record` 仍是五窗外／source-read=0 的 negative，因此不能把
  state transition 或畫面 hash 解讀成文字 consumer。

## 可重跑命令

以下命令只讀取 ROM；抽取輸出是被忽略的本機原文表：

```sh
/usr/bin/python3 -m unittest discover \
  -s games/tales-of-the-world-narikiri-dungeon-3/tests -v

/usr/bin/python3 games/tales-of-the-world-narikiri-dungeon-3/tools/recon_rom.py \
  games/tales-of-the-world-narikiri-dungeon-3/roms/base/Tales_of_the_World_Narikiri_Dungeon_3_JP_AGB-B3TJ-JPN.gba \
  --json > /private/tmp/tow-nd3-recon.json

/usr/bin/python3 games/tales-of-the-world-narikiri-dungeon-3/tools/extract_strings.py \
  games/tales-of-the-world-narikiri-dungeon-3/roms/base/Tales_of_the_World_Narikiri_Dungeon_3_JP_AGB-B3TJ-JPN.gba \
  --out games/tales-of-the-world-narikiri-dungeon-3/research/tales-of-the-world-narikiri-dungeon-3-decoded.jsonl

PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 \
  games/tales-of-the-world-narikiri-dungeon-3/tools/classify_pointers.py \
  games/tales-of-the-world-narikiri-dungeon-3/roms/base/Tales_of_the_World_Narikiri_Dungeon_3_JP_AGB-B3TJ-JPN.gba \
  --out /private/tmp/tow-nd3-pointers.json
```

若要在本機已有的、獨立 port mGBA GDB session 上重跑有界壓縮觀察：

```sh
/usr/bin/python3 games/tales-of-the-world-narikiri-dungeon-3/tools/runtime_probe.py \
  games/tales-of-the-world-narikiri-dungeon-3/roms/base/Tales_of_the_World_Narikiri_Dungeon_3_JP_AGB-B3TJ-JPN.gba \
  --port 24387 --max-calls 14 --wait-timeout 10
```

`runtime_probe.py` 只重用 `games/shining-soul-1/tools/gdbstub_client.py` 的
通用 GDB transport；B3TJ 的位址、ROM header 檢查與輸出欄位都在本目錄，沒有
套用《光明之魂》的 renderer 或文字格式。不要把 port shim、ROM、sav 或本機
JSONL 輸出加入 Git。

M1.5 consumer probe 需在本機自行啟動的 B3TJ mGBA GDB session 上執行；它改用
共用 `core/gba/gdbstub_client.py`，並只針對 `sjis:0x146EE0` 設 read watchpoint：

```sh
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 \
  games/tales-of-the-world-narikiri-dungeon-3/tools/consumer_probe.py \
  games/tales-of-the-world-narikiri-dungeon-3/roms/base/Tales_of_the_World_Narikiri_Dungeon_3_JP_AGB-B3TJ-JPN.gba \
  --port <your-independent-gdb-port> \
  --output /private/tmp/tow-nd3-m15.json
```

這個 probe 的 JSON 不含完整原文；只有 record 命中後才會在指定 ignored／
`/private/tmp` 目錄保存 VRAM、palette、OAM 與 IWRAM raw dump。

M1.6 resolver 回合仍使用同一個本作獨立 mGBA/GDB port；以下命令會在
`0x08003444` entry 與 `0x0800345C` return site 之間記錄 `r0/r1/lr`、resolved
`r0`，只對五窗內的 strict record 做分類，並同時 watch selected
`0x08146EE0`：

```sh
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 \
  games/tales-of-the-world-narikiri-dungeon-3/tools/consumer_probe.py \
  games/tales-of-the-world-narikiri-dungeon-3/roms/base/Tales_of_the_World_Narikiri_Dungeon_3_JP_AGB-B3TJ-JPN.gba \
  --port <your-independent-gdb-port> --trace-offset 0x146EE0 \
  --max-resolver-hits 24 --per-event-timeout 3 \
  --sequence start:12,none:20,down:12,none:10,a:12,none:20,right:12,none:10,a:12,none:20,left:12,none:10,b:12,none:10,up:12,none:10,select:8,none:10 \
  --output /private/tmp/tow-nd3-m16-selected.json
```

若要先取得候選再選 concrete record，可用 `--resolver-only`；若沒有 selected
record 命中，可用 `--trace-first-record` 對第一個實際返回的 strict-window
record 做有界 caller/source read trace。兩種模式都不做 runtime pointer scan。

M1.7 state probe 只觀察 state dispatcher 的單一 entry／return、KEYINPUT read
destination，以及 bounded screen hashes；它不覆寫 state bytes、不掃 resolver
指標，也不輸出 RAM/VRAM raw。breakpoint 必須在 mGBA reset stop 時安裝，才能
捕捉 boot→state 4 的 one-shot entry：

```sh
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 \
  games/tales-of-the-world-narikiri-dungeon-3/tools/state_probe.py \
  games/tales-of-the-world-narikiri-dungeon-3/roms/base/Tales_of_the_World_Narikiri_Dungeon_3_JP_AGB-B3TJ-JPN.gba \
  --port <your-independent-gdb-port> \
  --sequence start:1,none:300,a:1,none:300 \
  --max-events 602 --max-stops 2048 \
  --output /private/tmp/tow-nd3-m17-state.json
```

若 bounded sequence 在 state 4 handler 尚未 return 就耗盡，JSON 會標示
`open_dispatch.return_observed=false`；這是 negative navigation receipt，不能
當成正常 state transition。M1.7 的 static／runtime 邊界見
[`research/m17-state4-navigation-20260816.md`](research/m17-state4-navigation-20260816.md)。

M1.8 使用 [`tools/m18_a1ac_probe.py`](tools/m18_a1ac_probe.py) 做窄 bounded
navigation：在 A030 loop 後才掛 KEYINPUT read-watch，先送一次正常 START
`0x03F7` 完成 state 4 gate，再在 live `0x0800A1AC` 後送一次 A `0x03FE`；
後續只允許有限 `0x03FF` release。它記錄每次 `P1` 的 `OK` response、
`0x030033F8`、object `+0x54`、A2C0、`0x08005E12` 與固定畫面 hash，不寫
state/object/save，也不輸出 raw bytes：

```sh
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 \
  games/tales-of-the-world-narikiri-dungeon-3/tools/m18_a1ac_probe.py \
  games/tales-of-the-world-narikiri-dungeon-3/roms/base/Tales_of_the_World_Narikiri_Dungeon_3_JP_AGB-B3TJ-JPN.gba \
  --port <your-independent-gdb-port> --per-stop-timeout 30 \
  --max-stops 64 --max-edge-checks 8 --release-reads 3 --max-steps 12 \
  --output /private/tmp/tow-nd3-m18-a1ac.json
```

M1.8 的完整 confirmed／provisional／negative／unknown receipt 見
[`research/m18-a1ac-runtime-20260816.md`](research/m18-a1ac-runtime-20260816.md)。
成功 return 後再以全新 mGBA session 執行既有 resolver trace-first：

```sh
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 \
  games/tales-of-the-world-narikiri-dungeon-3/tools/consumer_probe.py \
  games/tales-of-the-world-narikiri-dungeon-3/roms/base/Tales_of_the_World_Narikiri_Dungeon_3_JP_AGB-B3TJ-JPN.gba \
  --port <your-independent-gdb-port> --trace-first-record \
  --max-resolver-hits 24 --per-event-timeout 5 \
  --output /private/tmp/tow-nd3-m18-trace-first.json
```

此 clean rerun 的 4 個 resolver return 均在五窗外，`source_read_count=0`、
`caller_return_count=0`；下一步是 state 7 的真正 text consumer，不是擴大
pointer scan 或開始翻譯。

若要重跑 state7 的 bounded readiness boundary，可在本作自有 mGBA GDB session 上執行：

```sh
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 \
  games/tales-of-the-world-narikiri-dungeon-3/tools/state7_readiness_probe.py \
  games/tales-of-the-world-narikiri-dungeon-3/roms/base/Tales_of_the_World_Narikiri_Dungeon_3_JP_AGB-B3TJ-JPN.gba \
  --port <independent-b3tj-gdb-port> --post-sequence none:256 \
  --post-max-events 256 --post-max-stops 300 \
  --output /private/tmp/tow-nd3-state7-readiness.json
```

完整界線見 [`research/m2-state7-readiness-runtime-20260816.md`](research/m2-state7-readiness-runtime-20260816.md)。

固定 renderer／loader candidates 的同日 natural-flow 邊界見
[`research/m2-natural-consumer-boundary-20260816.md`](research/m2-natural-consumer-boundary-20260816.md)。
`0x08001414`、`0x080014F4` 與 `0x080021A8` 在各自 bounded sequence 都沒有命中；
`--inject-record-offset 0x146EE0` 因 loader entry 未命中而沒有實際執行，不能當作
argument-injected pipeline 或 natural text consumer 證明。

shared runtime-validation framework 的 B3TJ case contract 與 static preflight 見
[`research/m2-runtime-case-20260816.md`](research/m2-runtime-case-20260816.md) 及
[`research/b3tj-clean-state4-runtime-case.json`](research/b3tj-clean-state4-runtime-case.json)。
manifest／static／report-safety 已通過；framework runtime actions 尚未執行，不能
把它或既有 game-specific receipt 當作完成的 localized text QA。
下一個窄 consumer contract 是
[`research/b3tj-state7-selected-record-runtime-case.json`](research/b3tj-state7-selected-record-runtime-case.json)：
它按正常 state4→state7 順序先停 parser callsite `0x08001D92`，再設置 parser
`0x080025CC` 與 selected record `0x08146EE0` read-watch；manifest/static 已通過，
但 runtime/source read 仍是 unknown。

M2 前置的 source-separated ledger 與控制標記 metadata 由
[`tools/ledger_metadata.py`](tools/ledger_metadata.py) 產生；提交的
[`translations/ledger.jsonl`](translations/ledger.jsonl) 只有 `source_hash`、
stable ID、區域／控制標記名稱與空白 targets。用 `--verify` 可在本機重新產生
source table 後檢查 decoder drift 與 hash mismatch；它不代表已解出碼頁，也不
允許在 renderer／容量證明前填入譯文。

固定 ROM literal／layout dispatch 的 provisional evidence 見
[`research/m2-static-layout-20260816.md`](research/m2-static-layout-20260816.md)，
摘要由 [`tools/static_layout_probe.py`](tools/static_layout_probe.py) 產生。它只
確認 66-pair table 的固定位置／雜湊與 19-entry dispatch 一致，仍未確認日文
codepage、glyph identity 或 runtime text consumer。

M2 另已完成一個更窄的 executable static edge：
[`research/m2-control-parser-20260816.md`](research/m2-control-parser-20260816.md)
與 [`research/m2-control-parser-metadata.json`](research/m2-control-parser-metadata.json)
記錄 `0x080025CC` 的 `%` command parser、`0x08002630` 的 84-entry bounded jump
table、IWRAM cursor `0x03001588`、NUL output 以及相鄰 width-helper candidate。
[`tools/control_parser_probe.py`](tools/control_parser_probe.py) 會驗證固定
signatures、target 範圍與 hash；這是 **confirmed-static control parser**，不是
live source consumer、日文 codepage、glyph identity 或回插證明。下一步仍是
在可重現 runtime 流程取得 parser entry 的 source pointer／caller receipt。

進一步的 direct-callsite receipt 見
[`research/m2-renderer-chain-20260816.md`](research/m2-renderer-chain-20260816.md)。
它確認全 ROM 只有 4 個 parser direct callsite，其中
`0x08001E26 → 0x080025CC → 0x08001DBC` 使用 bounded stack buffer 並寫入
IWRAM `0x03000060 + y*0x40 + x*2`；同一 static 區段的
`0x080014F4 → 0x08001414 → 0x080DDCC4 + index*0x20` 是 glyph source
candidate。`0x08001DBC` 不是 VRAM writer，後續搬運與 runtime source record 仍未
確認。可重跑工具是 [`tools/renderer_chain_probe.py`](tools/renderer_chain_probe.py)。

已知的 12-entry direct record table 另由
[`research/m2-record-table-20260816.md`](research/m2-record-table-20260816.md)
與 [`tools/direct_record_table_probe.py`](tools/direct_record_table_probe.py) 固定
驗證：12/12 target 都是 strict `text-pool` record，包含 selected
`sjis:0x146EE0`；但 target spacing 不等於容量證明，仍不可據此回寫或分類事件／
角色／服裝／技能／戰鬥／選單。

固定 caller 另揭出 control-only template `format:0x1474C0`：
[`research/m2-format-template-20260816.md`](research/m2-format-template-20260816.md)
記錄 code literal `0x0AEF1C → 0x081474C0 → 0x08001640 → 0x080025CC`；它只含
`%k` token、不是 strict record 起點，後面的 `sjis:0x1474C4` 才是另一筆
strict record。這類 template 不加入 8,938 筆 ledger，直到 template extractor、
token semantics 與 runtime read edge 都被證明。工具是
[`tools/format_template_probe.py`](tools/format_template_probe.py)。

`0x080014F4` 的另一條固定 byte→halfword lookup 邊由
[`research/m2-codepoint-lookup-20260816.md`](research/m2-codepoint-lookup-20260816.md)
記錄：`0x08004D90` 只由兩個 direct callsite 使用，並透過五個 ROM pointer slot
選取 bounded lookup windows。這是 codepoint lookup 的 static 證據，不是完整
日文 codepage、glyph identity、字寬或 runtime source edge；工具是
[`tools/codepoint_lookup_probe.py`](tools/codepoint_lookup_probe.py)。

另以 selected `sjis:0x146EE0` 做一個 record-level static path receipt：該筆 strict
record 只有 4 個 halfwidth units；固定 lookup helper（初始 lookup flag `0`）將其中
3 個 lookup result 導向 `0x080DDCC4 + index*0x20`，另 1 個 result 為
zero-combining／skip。這只確認 source-shaped bytes 在 ROM 靜態表上的 index／slot
算術，不確認遊戲是否實際消費該 record、slot 的 glyph 身分或 VRAM；詳情與 hash-only
輸出見 [`research/m2-static-record-font-path-20260816.md`](research/m2-static-record-font-path-20260816.md)
與 [`tools/static_record_font_path_probe.py`](tools/static_record_font_path_probe.py)。

固定的 asset／transform pipeline 另由
[`research/m2-font-pipeline-20260816.md`](research/m2-font-pipeline-20260816.md)
與 [`tools/font_pipeline_probe.py`](tools/font_pipeline_probe.py) 驗證：
`0x08001414` 以 `0x080DDCC4 + index*0x20` 選取固定 32-byte slot，依 parity
呼叫 `0x080011A8`／`0x080012E0`，兩者都使用 `0x03001464` 的 `&0x03` lookup
expansion 並寫向 `0x03000560` scratch。這是 confirmed-static transform shape，
不是 live record→glyph、完整 codepage、字寬或 scratch→VRAM 證明；其安全
receipt 只保留在 [`research/m2-font-pipeline-metadata.json`](research/m2-font-pipeline-metadata.json)。

可重跑命令：

```sh
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 \
  games/tales-of-the-world-narikiri-dungeon-3/tools/font_pipeline_probe.py \
  games/tales-of-the-world-narikiri-dungeon-3/roms/base/Tales_of_the_World_Narikiri_Dungeon_3_JP_AGB-B3TJ-JPN.gba \
  --out /private/tmp/tow-nd3-font-pipeline.json
```

下一個 runtime slice 已固定為
[`tools/font_consumer_probe.py`](tools/font_consumer_probe.py)：它只在
`0x08001414` entry 命中後，依 `r2` 的 `0x080DDCC4 + r2*0x20` 設單一 asset
read-watch，再 bounded 觀察 `0x080011A8`／`0x080012E0` 與 `0x03000560`。它
不做 resolver／pointer scan、不讀出 bytes，也不把沒有 runtime hit 的 harness
當成文字 source edge；界線與目前環境 negative 見
[`research/m2-font-consumer-probe-20260816.md`](research/m2-font-consumer-probe-20260816.md)。

另外已固定一條更接近 source pointer 的 static chain：全 ROM 只有一個
`0x08015C26 → 0x080021A8` direct caller，caller 將 builder input 經 `r8` 放入
loader `r1`，loader 讀 `[r1]`／`[r1+1]` 後選取
`0x080DDCC4 + index*0x20`。詳情與 metadata-only probe 見
[`research/m2-font-record-consumer-20260816.md`](research/m2-font-record-consumer-20260816.md)
與 [`tools/font_record_consumer_probe.py`](tools/font_record_consumer_probe.py)。
這仍是 source-pointer-shaped static edge；strict record membership、live read、
glyph identity 與 VRAM destination 尚未確認。

同一份 bounded probe 也固定了 caller-upward input shape：`0x080CD14C` 的 `r0`
保存至 `r5`，再由 `0x080CD170` 以 `r1=r5` 呼叫 `0x08015B74`；上游五個 direct
caller 的 input setup 只列為 static register metadata，不代表 strict record。下一次
runtime 只需在這條已確認鏈設單一 breakpoint，再追同一筆 `r1` 到 loader/source
watch；不增加 pointer scan 或幾何切片。

已另建立窄化的 runtime probe
[`tools/font_record_runtime_probe.py`](tools/font_record_runtime_probe.py)：它從
`0x080021A8` entry 只追該次 `r1` source pointer，在 `0x080021DA` 觀察計算完成的
`r8`，再對單一 asset slot 設 read-watch。它重用五窗 strict metadata，不做 runtime
pointer scan、不讀出 source／glyph bytes，也不寫 state、object、save 或 ROM。可在
本作獨立 mGBA port 上重跑：

```sh
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 \
  games/tales-of-the-world-narikiri-dungeon-3/tools/font_record_runtime_probe.py \
  games/tales-of-the-world-narikiri-dungeon-3/roms/base/Tales_of_the_World_Narikiri_Dungeon_3_JP_AGB-B3TJ-JPN.gba \
  --port <your-independent-gdb-port> --max-events 602 --max-stage-stops 12 \
  --output /private/tmp/tow-nd3-m2-font-record-runtime.json
```

若要在同一 bounded session 先觀察已確認 caller-upward 的 input provenance，可加
`--trace-builder-input --max-builder-hits 4`。它只在 `0x08015B74` 記錄 `r1`、LR
與 strict-window classification，仍不讀 source bytes；命中後才繼續同一個 loader
entry/source/asset pipeline。builder hit 本身不是自然文字 consumer proof。

為縮小下一次 state 7 runtime breakpoint，新增
[`tools/state7_static_callpath.py`](tools/state7_static_callpath.py)：它只驗證兩條
固定 direct-BL chain，分別到 formatter `0x080014F4` 與 parser `0x080025CC`，不做
新的 pointer scan，也不把 static chain 當作 natural-flow source read。詳情見
[`research/m2-state7-static-callpath-20260816.md`](research/m2-state7-static-callpath-20260816.md)。

為了把另一條已確認的 formatter edge 收斂成一個可重跑切片，新增
[`tools/format_record_runtime_probe.py`](tools/format_record_runtime_probe.py)。它只
在 `0x080014F4` 設 entry breakpoint；命中後先要求 `r0` 是五窗內的 exact strict
record 起點，才安裝該筆 source read-watchpoint。之後最多觀察一次
`0x08004D90` codepoint lookup、一次 `0x08001414` font-map／asset slot read、一次
`0x03000560` scratch write，並保留 caller LR、register snapshot、地址分類與
hash/count metadata。`--trace-first-strict` 只把第一個實際命中的 strict record
當成目標；它不掃 resolver／pointer、不輸出 source 或 glyph bytes，也不寫
state/object/save。測試見
[`tests/test_format_record_runtime_probe.py`](tests/test_format_record_runtime_probe.py)。

這個 probe 的 offline contract 與目前狀態見
[`research/m2-format-record-runtime-20260816.md`](research/m2-format-record-runtime-20260816.md)。
目前沒有 selected strict record 的 live hit：乾淨 standard mGBA listener 從 reset
實際跑過 72 個 bounded KEYINPUT events，ROM identity `B3TJ`／CRC32 `1867CCEF`、
strict count `8938` 通過，但 `0x080014F4` format hits、source read、lookup、asset
與 scratch hits 均為 `0`。先前受 sandbox 限制的 invocation 則是
`PermissionError` setup negative；另一次在 M1.8 正常 state 4→7 後重新連線時，
mGBA 0.10 對第二個 GDB client 的 `qSupported` timeout。兩者都不能當成 renderer
或 codepage 的 negative proof；`m18_a1ac_probe.py --trace-format-after-return` 已
在同一 GDB connection 合併 navigation 與 formatter trace，state 7 的
`none:64,a:8,none:56`／128-event bounded sequence 仍是 format hit 0。下一個最小
切片是固定 `0x080025CC` parser/caller，不再增加 formatter geometry。

目前 parser slice 已收斂為 [`tools/parser_record_runtime_probe.py`](tools/parser_record_runtime_probe.py)。
它只在固定 `0x080025CC` entry 觀察 direct-caller LR、`r0`／`r1` 分類與
`0x03001588` cursor；只有 `r1` 是五窗內 exact strict record start 才安裝 source
read-watch，RAM `r0` 只作 output-write candidate，並以 `0x08001DBC` 作 IWRAM
writer breakpoint。`m18_a1ac_probe.py --trace-parser-after-return` 會沿正常 state
4→7 return 在同一 GDB connection 執行 bounded sequence；本次 fresh invocation
在 socket setup 得到 `PermissionError: [Errno 1] Operation not permitted`，所以
沒有 parser／source／output／writer hit。這是 setup boundary，不是 parser 或遊戲
沒有文字的證據；詳情見
[`research/m2-parser-runtime-20260816.md`](research/m2-parser-runtime-20260816.md)。

2026-08-16 的 port `24387` setup receipt 仍是 runtime negative：ROM identity／strict
count `8938` 通過，但 sandbox 回報 `PermissionError: [Errno 1] Operation not
permitted`，一次外部重試仍無 loader stop。詳情見
[`research/m2-font-record-runtime-20260816.md`](research/m2-font-record-runtime-20260816.md)
與 [`research/m2-font-record-runtime-metadata.json`](research/m2-font-record-runtime-metadata.json)。
因此 M2 live renderer／decoder 項目仍未完成，不能開始翻譯或回插。

其後兩次各自新啟動的 B3TJ mGBA process 使用獨立 port `24388` 重跑同一 probe：
分別嘗試 `gdb.port` 與 `ports.qt.gdbPort` 設定鍵，均在 setup 得到
`OSError errno 49: Can't assign requested address`，loader/source/asset hits 都是
`0`。`--inject-record-offset 0x146EE0` 只完成 strict-start metadata 驗證，因沒有
loader entry hit 並未改寫寄存器；這是 listener/setup negative，不能升格為自然
consumer 或注入 pipeline 證據。兩個自有 process 均已停止，receipt 詳見同一份
[`research/m2-font-record-runtime-20260816.md`](research/m2-font-record-runtime-20260816.md)
與 metadata JSON。

若自然流程難以觸發 loader，可用同一 probe 的
`--inject-record-offset 0x146EE0` 模式，只在 loader entry 已命中後把 `r1` 暫時
改成一個**已確認 strict record 起點**。此模式只驗證
`injected source→loader→asset` pipeline，報告會標成
`injected-source-pipeline-only`，不能當作自然遊戲 text-consumer 或正常 navigation
證據；CLI 會拒絕非 strict offset 或任意 RAM 位址注入。

同一 loader 的固定輸出幾何另由
[`tools/font_loader_layout_probe.py`](tools/font_loader_layout_probe.py) 驗證：
單一 `0x20`-byte asset slot 的 `+0x00/+0x10` half 經
`0x03001464` lookup shape，寫入 caller context 的 `+0x00/+0x20/+0x40/+0x60`
四組 `0x20` bytes（總 `0x80` bytes）。這只是 **confirmed-static byte geometry**，
不代表 glyph identity、bpp／字寬、完整 codepage、live source consumer 或
context→VRAM；receipt 見
[`research/m2-font-loader-layout-20260816.md`](research/m2-font-loader-layout-20260816.md)。

已建立第一個**不等同翻譯 builder** 的 fail-closed 等長 round-trip POC：
[`tools/bounded_roundtrip_poc.py`](tools/bounded_roundtrip_poc.py) 只接受 exact strict
record start、同長 replacement bytes、NUL terminator 與 control/newline invariant，
在記憶體重抽取後才寫 ignored／`/private/tmp` patched ROM。對 selected
`sjis:0x146EE0` 的 synthetic 4-byte payload，8,938 筆 record starts、untouched
records 與 outside-span bytes 均保持一致；再重用
[`core/patches/bps_create.rb`](../../core/patches/bps_create.rb)／`bps_apply.rb` 做
BPS byte-identical apply。這只證明 bounded static mechanics，尚未證明 live consumer、
codepage／glyph、容量／指標／壓縮或可開始翻譯；receipt 見
[`research/m2-roundtrip-poc-20260816.md`](research/m2-roundtrip-poc-20260816.md)。

```sh
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 \
  games/tales-of-the-world-narikiri-dungeon-3/tools/ledger_metadata.py \
  games/tales-of-the-world-narikiri-dungeon-3/research/tales-of-the-world-narikiri-dungeon-3-decoded.jsonl \
  --ledger-out games/tales-of-the-world-narikiri-dungeon-3/translations/ledger.jsonl \
  --metadata-out /private/tmp/tow-nd3-ledger-summary.json --verify
```

## 外部工程參考

[Kajitani-Eizan 的舊專案頁](https://www.blade2187.com/projects/narikiri-dungeon-3/)
只作為「曾有 v1.11、偏選單／開頭的部分 patch」工程背景；它不是本專案的完整
翻譯來源，也不替代本 ROM 的格式驗證。
