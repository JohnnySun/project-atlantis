# 《真・女神轉生 II》漢化工作區

本目錄只處理日版 GBA《真・女神転生II》（A5TJ），目標為臺灣繁體 `zh-TW`。ROM、sav、完整解出的原文、VRAM／OAM dump、渲染圖片與暫存構建只保存在本機，不進 Git。

## M0/M1/M1.5/M1.6/M1.7/M1.8/M1.9 基準狀態（2026-08-16）

- ROM header 身分已確認：`DDS_2`、`A5TJ`、maker `EB`、revision `0`、8 MiB。
- 本機候選的 ROM CRC32 為 `af40cc99`，SHA-256 為 `819a6a19a40bfbe7608f4b813dc18285c827f64e1523561ffe8e10ce8ab5991e`；完整指紋和 header complement 異常見 `research/recon-20260816.md`。
- header complement 儲存值 `0x4a`、依標準公式計算值 `0x7c` 不一致；mGBA 仍能執行並顯示畫面，因此本階段不修改 ROM，也不把「可執行」誤當成 dump 來源乾淨的證明。
- `tools/recon_static.py` 是本作自有的唯讀第一輪掃描器：接受 raw GBA 或只有一個 GBA 成員的 ZIP，只輸出 header、雜湊、尾端、候選計數與偏移，不輸出完整原文。
- 2367 headless GDB 回合已完成：讀取 watchpoint 確認 KEYINPUT 消費點；Start 輸入後讀取 VRAM、palette、OAM，並依 OAM 實際排列渲染出遊戲內日文免責文字。
- M1.5 已完成一個有界來源分析回合：Start 後有 46 個 active sprite、84 個 unique OBJ tile；完整 sprite glyph 在 ROM、IWRAM、EWRAM 與 bounded LZ77/RL stream 均無 byte-identical match，也沒有因此推導出 font stride。
- 已確認 OAM buffer 的 IWRAM source 與 DMA3→OAM consumer；OBJ tile 的固定 DMA candidate 已記為 provisional，尚未宣稱是免責畫面的實際 source。
- 目前只確認「文字確實在 OBJ sprite 路徑上被消費並顯示」；尚未確認文字儲存表、codepage、指標／bank、壓縮、控制碼、惡魔／技能／道具／劇情資料邊界或可逆回插路徑。
- M1.6 已把 provisional `0x080baecc` 完整驗證為固定 9-instruction Thumb DMA3 setup：literal pool 在 `0x080baee0`–`0x080baef0`，固定 `0x02001000` → `0x06013000`、control `0x84000700`；它不是 queue parameter。其餘七個 `0x06013000` copy 也是同一個 byte pattern 的固定副本；先前記為 `0x080bbcdc` 等五個位址的是 routine 的第一條 source `STR`，真正 entry 已在研究紀錄中回退 4 bytes。
- M1.6 已確認一個獨立的通用 resource/event queue：drain `0x080ad01c`、producer `0x080ad0fc`、base `0x02009004`、64 個 stride `0x64` entry、callback table `0x0815eeec`。reset→Start live entry `0x02009068`／`0x020090cc` 只攜帶 ROM resource pointers `0x08509cf8`／`0x08509cd0`；這不是已證明的 glyph transfer queue。
- M1.6 的 formal bounded probe 在 35 秒 reset→Start window 讀到 KEYINPUT 6 次、送出 Start；八個固定 OBJ-DMA site、`0x080baef0` staging candidate 與 `0x02001000` write watch 都是 0 hit。DMA3 register、queue entry、queue callback 與 BIOS LZ77 consumer 的 metadata 有捕捉，但唯一 LZ77 目的地為 `0x0200f874`，不是 staging buffer。這是可重現的陰性窗口，不是「全遊戲沒有」的證明。
- `0x080baef0` 仍是最精確的 glyph-staging candidate：兩次 `LZ77UnCompWram` wrapper call 目標分別為 `0x02001000` 與 `0x02002000`；它在本次畫面窗口未命中。附近 `0x081869c8` descriptor 的自然 command drain 仍待以 live indirect dispatch 追蹤，不能把 table pointer 當成 source table。
- M1.7 已完成 descriptor／selector 有界切片：`0x08182b70` 是
  `0x08182b54 + 7*4`，選出的 descriptor 為 `0x081869c8`；selector
  `0x080ba8d8` 的三個 direct BL caller、ARM7TDMI boundary、literal pool、
  callback table `0x0815eeec`（25×8）與 descriptor sentinel stream 均已記錄於
  `research/m1.7-descriptor-20260816.md`。descriptor window 是 variable-length，
  不是固定 stride，也沒有因此建立 source table。
- M1.7 natural A/Start/方向鍵 transition 未命中三個 selector caller、
  `0x080baef0` 或 `0x080bafb8`；generic queue 的 source/LZ77 activity 仍是
  `0x08509cf8`／`0x08509cd0` 與 `0x084f9cd0 → 0x0200f874`。一個明確標記的
  synthetic `group=1,index=7` fallback 只確認
  `0x081869c8 → 0x080ad0fc(pointer,0xffff)` producer link，並在 return guard
  fail-closed；不能冒充自然 resource selection，也沒有取得 glyph writer。
- 尚未開始翻譯，也沒有可提交的翻譯記錄；專有名詞會在真正建立批次前依 `AGENTS.md` 查 Wikipedia zh-tw、巴哈姆特及其他獨立來源。
- M1.8 已從 fresh process 起點先 arm `0x03006950` pointer、相鄰 halfword 與 `0x0203db40` counter watches；三條明確 natural transition cohort 與同一路徑的窄 initializer-only follow-up 都沒有 pointer/counter write、selector caller 或 descriptor hit。完整證據與 22 個 provisional static candidates 見 `research/m1.8-selector-initializer-20260816.md`。
- M1.9 已完成四個 priority writer 的 bounded Thumb static mapping 與 caller 1–3 層：`0x0813e428` 以 incoming `r0` 替換 selector pointer、`0x0813e574` 從 RAM `0x030068c0` 還原，`0x0812f2b4` 的明確分支則寫入 ROM `0x08036666`；`0x080bee40`／`0x081534ae` 的 caller argument 只得到 provisional ROM-table provenance，尚未連到 glyph source。證據見 `research/m1.9-selector-state-mapping-20260816.md`。

## 可重現入口

在本機合法持有的日版候選檔案上執行：

```sh
python3 games/shin-megami-tensei-2/tools/recon_static.py /path/to/A5TJ.zip --pretty
```

M1.6 的固定 DMA／queue 靜態驗證不會做 glyph pattern scan：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B \
  games/shin-megami-tensei-2/tools/m16_queue_probe.py \
  --rom /path/to/A5TJ.gba --static-only \
  --output /private/tmp/smt2-m16-static.json
```

若要重跑已啟動、且只屬於本作的 mGBA GDB port `2367`，runtime report 只保留
address、PC/LR、selected registers、length、hash 與 count；不要把 output 放進 Git：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B \
  games/shin-megami-tensei-2/tools/m16_queue_probe.py \
  --rom /path/to/A5TJ.gba --port 2367 --press-start \
  --output /private/tmp/smt2-m16-runtime.json
```

可以再以 `--summary --input-report` 產生可放入研究筆記的 metadata 摘要。

M1.7 selector／descriptor 靜態與 bounded runtime 入口：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B \
  games/shin-megami-tensei-2/tools/m17_descriptor_probe.py \
  --rom /path/to/A5TJ.gba --static-only \
  --output /private/tmp/smt2-m17-static.json

PYTHONDONTWRITEBYTECODE=1 python3 -B \
  games/shin-megami-tensei-2/tools/m17_descriptor_probe.py \
  --rom /path/to/A5TJ.gba --port 2367 --lean-transition \
  --key-sequence a,start,a,b,down,a \
  --output /private/tmp/smt2-m17-runtime.json
```

`--force-selector-index 7` 是只供工程驗證的 synthetic、fail-closed fallback；
它會明確標示 PC/register override，不得當成自然場景證據，也不應在未審核的
遊戲狀態上繼續 emulator 執行。

M1.8 initializer／natural transition probe：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B \
  games/shin-megami-tensei-2/tools/m18_initializer_probe.py \
  --rom /path/to/A5TJ.gba --port 2345 --path-id boot-start \
  --key-sequence a,start,a,b,down,a --output /private/tmp/smt2-m18.json

PYTHONDONTWRITEBYTECODE=1 python3 -B \
  games/shin-megami-tensei-2/tools/m18_initializer_probe.py \
  --rom /path/to/A5TJ.gba --port 2345 --initializer-only \
  --key-sequence a,start,a,b,right,left,down --output /private/tmp/smt2-m18-init.json
```

`--initializer-only` 只保留 initializer candidates 與窄 selector-table watches；
它沒有任何 selector/state 寫入選項。`--summary --input-report` 可產生不含事件
payload 的 metadata 摘要。

M1.9 selector state mapping（唯讀 static）：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B \
  games/shin-megami-tensei-2/tools/m19_state_mapping.py \
  --rom /path/to/A5TJ.gba --output /private/tmp/smt2-m19-static.json
```

工具只追 M1.8 已列出的四個 writer、tracked global literal/store 與最多三層
Thumb BL caller；它不做 glyph scan、不輸出 instruction/raw source，也不建立
source table。

本回合優先使用專案共用的 `core/gba/gdbstub_client.py`、
`core/gba/capture_runtime.py`、`core/gba/render_oam.py` 與本目錄的
`tools/analyze_obj_tiles.py`、`tools/trace_swi_consumers.py`、
`tools/trace_dma_consumers.py`。共用工具只負責 GDB remote protocol 與標準 GBA
memory/tile/OAM 操作；A5TJ 的 offset、來源判定與 negative evidence 均記在本目錄，
沒有套用其他遊戲的 ROM 格式假設。

## 下一個安全切片

沿 M1.9 確認的 RAM save/restore edge，先對 `0x08198a98`、`0x087df54c` 兩個
provisional ROM pointer-table provenance 做 bounded table-shape／caller mapping，
再決定是否有不重複 runtime window 的最小自然 transition。仍不得把 selector
state table 當成文字 source；只有 decoder 能穩定重新抽出同一批資料、且回插後能
byte-for-byte 驗證，才進入有限量翻譯與 patch 工程。
