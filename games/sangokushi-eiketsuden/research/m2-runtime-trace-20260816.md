# M2 bounded runtime trace：第一個可選短 record

日期：2026-08-16（Asia/Taipei）

本切片只處理《三國志英傑伝》B3EJ，不建立《孔明伝》資料，也不建立翻譯批次。
目標是從一組已知 Shift-JIS 候選池選出一個短 record，沿著「ROM pointer／record
→ runtime read → glyph/tile writer 或 renderer delta」取得可審核證據。這次 runtime
入口在連線前失敗，因此下文不把靜態候選或 trace harness 當成已完成的 runtime link。

## 選定的 static candidate

本切片選用 ledger 中的 table B（工具標籤
`menu_battle_candidate_a`）entry `0`：

| 欄位 | 值 | 意義／限制 |
|---|---:|---|
| table file offset | `0x0D1FFC` | 四組候選中的 menu／battle pool B |
| pointer entry | `0` | pointer word 位址為 GBA `0x080D1FFC` |
| pointer target file offset | `0x078528` | runtime ROM 位址 `0x08078528` |
| payload length | `14` bytes | 不含 `0x00` terminator；短 record |
| payload SHA-256 | `c7ac47044e9576475f854841981b18ae20eca25ad41df403164ee6307b1aecca` | 只作本機 source drift receipt，不保存原文 |
| Shift-JIS decode | valid | 7 個日文字元的靜態候選；本表不保存字串內容 |
| context hypothesis | 早期戰役的單部隊／低威力效果描述 | 由相鄰 static pool 分類推定，尚未由畫面核對 |

選 B[0] 是因為它是候選池中短、可由標準 Shift-JIS 解碼、且語意接近早期戰鬥效果
訊息的 record。這仍只是選樣理由；`0x0D1FFC` 尚未被 runtime read watchpoint
命中，不能稱為遊戲實際使用的文字表。table C 的相鄰候選在先前 static 檢查呈現
檔名／資源索引形態，本切片不把它當作劇情或戰鬥文本。

## 可重跑工具

新增 `tools/trace_m2_runtime.py`，只負責這個 bounded candidate：

- 透過 `core/gba/gdbstub_client.py` 建立單一 GDB client；沒有複製 packet transport。
- 對 `KEYINPUT` read、pointer word `0x080D1FFC` read、record start
  `0x08078528` read 設 watchpoint。
- 以 active-low `none:5,start:4,none:12` 送出有限按鍵序列；只覆寫當次 KEYINPUT
  read 的 CPU `r0`，不寫 ROM 或 save。
- 每個 stop 只輸出 PC、LR、stop address、register snapshot，以及是否有 register
  等於 record pointer 的關係；不輸出原始 bytes 或解碼文字。
- 以共用 client 讀取前後 VRAM，只輸出 SHA-256、變動 byte 數、變動 4bpp tile
  數與 I/O 設定。需要視覺核對時，另用共用 `core/gba/render_vram.py` 處理 ignored
  capture；本工具不重寫 renderer。

可重現的靜態契約測試：

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest \
  games/sangokushi-eiketsuden/tools/test_trace_m2_runtime.py -v
```

實際 runtime session 需由操作者以自己的 mGBA process 與獨立 port 啟動，再執行：

```text
PYTHONDONTWRITEBYTECODE=1 python3 \
  games/sangokushi-eiketsuden/tools/trace_m2_runtime.py \
  games/sangokushi-eiketsuden/roms/base/B3EJ_JP_candidate.gba \
  --port <本 session 的獨立 GDB port> \
  --output games/sangokushi-eiketsuden/work/m2-trace.json
```

`work/m2-trace.json` 只能是本機 ignored artifact；它可能含 runtime registers 與
hash，不可加入 Git。任何成功報告仍要由 pointer hit、record hit、register value
關係和 renderer／VRAM delta 一起審核，不能只看 `link_status` 字串。

## 本次 runtime 嘗試

### Confirmed

- ROM identity、B3EJ header、標準 Shift-JIS 靜態候選、四組 pointer table 的 file
  offsets 與 target ranges，仍以 `research/recon-ledger.md` 的既有證據為準。
- table B entry 0 的 pointer／target／payload length／SHA-256 可由
  `trace_m2_runtime.py` 的 `static_candidate_metadata()` 重新核對；這是
  `confirmed-static`，不是 runtime consumer proof。
- 先前成功的共用 capture 仍只確認標題畫面可執行、Mode 0、BG0–BG3 screenbase
  與 title renderer delta；它沒有把 B[0] 或其他 static record 連到文字 writer。
- 本次所有自建 mGBA 子進程均由本 session 的 probe 在結束路徑清理，沒有停止其他
  session 的 process，也沒有產生應提交的 ROM、save、source dump 或圖片。

### Provisional

- B[0] 很可能屬於 menu／battle effect pool，且是適合早期戰鬥畫面驗證的短 record；
  這是 table layout、Shift-JIS 可解碼性和相鄰語意的交集推定。
- **Glyph addressing**：目前只有 runtime GBA BG／tilemap 渲染參數的 title-screen
  證據；沒有確認字型 ROM base、glyph index、cell stride、tile writer 或 record
  到 tilemap 的轉換公式。
- **Unicode identity**：該 payload 可用標準 Shift-JIS 解成 7 個 Unicode 字元，這
  只確認靜態 byte-level codepage interpretation；沒有把任何字元與 runtime glyph
  tile、font slot 或實際畫面位置逐字核對。因此 Unicode 解碼與 glyph identity
  必須維持兩個獨立欄位，不能將「可解 Shift-JIS」寫成「字型已解決」。

### Negative

- headless mGBA build 的獨立 port `39123`：本次 input probe 在部分啟動中等不到
  listener，另一次雖建立 socket 但 `?` 初始 GDB request timeout；重試仍未取得
  可用單一 session。這只否定本次 probe 的啟動可靠性，不否定 B3EJ ROM identity。
- 既有 SDL mGBA build（預設 GDB `2367`，以本 session 的暫存 bind shim 改到
  `24388`）在有／無 dummy video 的 bounded 啟動中均以 `SIGSEGV (-11)` 結束，
  尚未建立 GDB listener。
- 既有 Qt mGBA build（預設 GDB `2345`，以既有暫存 bind shim 改到 `24387`）在
  offscreen 與正常圖形環境兩次 bounded 啟動中均以 `SIGSEGV (-11)` 結束，尚未
  建立 GDB listener。
- 因沒有成功連上本 session 的 runtime，`0x080D1FFC` 沒有 read-watchpoint hit，
  `0x08078528` 沒有 record read hit，沒有可以比對 `r0`／其他 register 的 source
  pointer 關係，也沒有 menu／早期戰役導航後的 VRAM renderer delta。
- 因此本切片**沒有證明**「source pointer／record → runtime glyph/tile writer」；
  不把 pointer 靜態合法性、title BG 重建或 trace harness 的存在升級成
  `confirmed-runtime`。

## 邊界與下一步

本次不產生 `research/*-decoded.jsonl`、translation ledger、source table 或回插
工具。下一次應在圖形／GDB runtime 可穩定啟動後，直接使用本工具驗證 B[0]；至少要
取得：

1. pointer entry read stop，且 register 中能對上 `0x08078528` 或可由 PC／LR 呼叫
   context 證明其載入結果；
2. 同一導航序列中的 record read stop，記錄 reader PC／LR；
3. 同一時間窗的 VRAM delta 或 writer／DMA destination 證據，並用共用 renderer
   確認畫面不是單純 title BG；
4. 一個已知畫面字元對應的 glyph tile／Unicode cross-check，分開更新
   `glyph addressing` 與 `Unicode identity`。

在上述交叉證據和未修改 round-trip 以前，字串結構、控制碼、字型和可逆回插仍維持
`blocked-on-structure`，不開始翻譯批次。
