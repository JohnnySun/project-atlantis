# M2 source-shaped font-loader runtime slice（2026-08-16）

## 範圍

本回合沒有擴大 pointer scan，也沒有修改 state、object、save 或 ROM。可重跑工具
是 [`tools/font_record_runtime_probe.py`](../tools/font_record_runtime_probe.py)，只
重用 [`core/gba/gdbstub_client.py`](../../../core/gba/gdbstub_client.py) 的既有
GDB transport。工具在 loader entry `0x080021A8` 取得該次呼叫的 `r1`，只對該
位址設一個 byte read-watch；到固定的 `0x080021DA`（`r8` 已完成 asset address
計算後的下一個 Thumb 指令）再對該次 `r8` asset slot 設一個 byte read-watch。
輸出只有位址、strict record metadata、寄存器、stop metadata 與計數，不包含 source
或 glyph bytes。

strict record classification 直接重用本作 `consumer_probe.py` 的五個已核准資料窗
與本機 strict extractor；因此只有 `r1 ==` 某一筆 strict record 起點時，才會保留
`string_id`。window 內非起點、RAM input、ROM window 外位址都維持各自 negative
分類，不會被高位 asset address 取代。

## runtime receipt

本日對本作獨立 port `24387` 做了一次 bounded setup 嘗試，ROM 只讀驗證仍通過：

| 欄位 | 結果 |
| --- | --- |
| ROM | `TOWNARIKIRI3` / `B3TJ` / `AF` / 16 MiB |
| CRC32 | `1867CCEF` |
| strict record count | `8938` |
| sequence | `start:1,none:63`（最多 64 event） |
| loader entry hits | `0` |
| source read hits | `0` |
| asset read hits | `0` |
| default sandbox setup | `PermissionError`，`[Errno 1] Operation not permitted` |
| one permitted external retry | `OSError`，仍無 loader stop |

因此本回合沒有 live source consumer、strict record provenance 或 glyph read 證據。
這是 **runtime setup negative**，不是 `0x080021A8` consumer 的 runtime negative；
不能把 fake client 測試中的合成 stop 當成遊戲命中，也不能宣稱 codepage、glyph
identity、RAM decoder、VRAM writer 或回插成立。另一個權限重試在工具審核串流中斷後
未被允許，沒有再使用其他 process、port 或 transport workaround。

之後又以兩個全新的、只由本回合啟動的 mGBA process 重跑同一個 bounded probe，均使用
獨立 port `24388` 與 `--inject-record-offset 0x146EE0`；第一次使用 `gdb.port` 設定
鍵，第二次使用既有 Qt `ports.qt.gdbPort` 設定鍵。兩次都在 client setup 得到
`OSError`／errno `49`（`Can't assign requested address`），`loader_hits=0`、
`source_read_hits=0`、`asset_read_hits=0`。注入選項只完成 ROM-side strict-start
驗證，因為 loader entry 根本沒有命中，所以沒有產生任何注入 source read；這仍是
**listener/setup negative**，不是自然流程或注入 pipeline 的 runtime proof。兩個
自有 process 都已由各自的 bounded harness 停止，沒有接觸其他 session。

## offline contract

`tests/test_font_record_runtime_probe.py` 以 fake client 重演三個 bounded stop：

1. strict `sjis:0x146EE0` 的 source read；
2. `0x080021DA` 的 `r8=0x080E00C4` asset address-ready；
3. 該單一 asset slot 的 read watch。

測試只驗證 probe 的清理、分類與 metadata 欄位，不提供 runtime evidence。新增的
source-shaped loader harness 為 **confirmed tooling contract**；以下工程邊界仍是
**unconfirmed**：

- live strict source read、RAM decoder/output buffer、glyph identity；
- codepage、字寬、控制碼語義、文字 VRAM destination；
- event／角色／服裝／技能／戰鬥／選單分類；
- 容量、指標重寫、壓縮邊界、round-trip、BPS 與翻譯。

下一個最小切片不是再增加 port shim 或 static geometry，而是沿已確認的
`0x08015C26 → 0x080021A8` caller 向上固定其 input provenance，或在已有可連線的
本作獨立 mGBA session 上重跑同一工具；一旦取得第一個真實 loader hit，只追該次
source watch 往下一個 decoder/output stop。在此之前 M2 的 live renderer 項目保持未
完成，M3 不得開始填入譯文。

若自然流程仍難以觸發 loader，可加 `--inject-record-offset 0x146EE0`。此模式只在
loader entry 已命中後寫入 `r1`，且 CLI 會拒絕非 strict record 起點；所有 receipt
會標為 `runtime-argument-injected`／`injected-source-pipeline-only`。它可補足
loader→asset→decoder 的 runtime pipeline，但不等同自然流程的 text consumer，
也不會改寫 state、object 或 save。
