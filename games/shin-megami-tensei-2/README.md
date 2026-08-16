# 《真・女神轉生 II》漢化工作區

本目錄只處理日版 GBA《真・女神転生II》（A5TJ），目標為臺灣繁體 `zh-TW`。ROM、sav、完整解出的原文、VRAM／OAM dump、渲染圖片與暫存構建只保存在本機，不進 Git。

## M0/M1/M1.5 基準狀態（2026-08-16）

- ROM header 身分已確認：`DDS_2`、`A5TJ`、maker `EB`、revision `0`、8 MiB。
- 本機候選的 ROM CRC32 為 `af40cc99`，SHA-256 為 `819a6a19a40bfbe7608f4b813dc18285c827f64e1523561ffe8e10ce8ab5991e`；完整指紋和 header complement 異常見 `research/recon-20260816.md`。
- header complement 儲存值 `0x4a`、依標準公式計算值 `0x7c` 不一致；mGBA 仍能執行並顯示畫面，因此本階段不修改 ROM，也不把「可執行」誤當成 dump 來源乾淨的證明。
- `tools/recon_static.py` 是本作自有的唯讀第一輪掃描器：接受 raw GBA 或只有一個 GBA 成員的 ZIP，只輸出 header、雜湊、尾端、候選計數與偏移，不輸出完整原文。
- 2367 headless GDB 回合已完成：讀取 watchpoint 確認 KEYINPUT 消費點；Start 輸入後讀取 VRAM、palette、OAM，並依 OAM 實際排列渲染出遊戲內日文免責文字。
- M1.5 已完成一個有界來源分析回合：Start 後有 46 個 active sprite、84 個 unique OBJ tile；完整 sprite glyph 在 ROM、IWRAM、EWRAM 與 bounded LZ77/RL stream 均無 byte-identical match，也沒有因此推導出 font stride。
- 已確認 OAM buffer 的 IWRAM source 與 DMA3→OAM consumer；OBJ tile 的固定 DMA candidate 已記為 provisional，尚未宣稱是免責畫面的實際 source。
- 目前只確認「文字確實在 OBJ sprite 路徑上被消費並顯示」；尚未確認文字儲存表、codepage、指標／bank、壓縮、控制碼、惡魔／技能／道具／劇情資料邊界或可逆回插路徑。
- 尚未開始翻譯，也沒有可提交的翻譯記錄；專有名詞會在真正建立批次前依 `AGENTS.md` 查 Wikipedia zh-tw、巴哈姆特及其他獨立來源。

## 可重現入口

在本機合法持有的日版候選檔案上執行：

```sh
python3 games/shin-megami-tensei-2/tools/recon_static.py /path/to/A5TJ.zip --pretty
```

本回合優先使用專案共用的 `core/gba/gdbstub_client.py`、
`core/gba/capture_runtime.py`、`core/gba/render_oam.py` 與本目錄的
`tools/analyze_obj_tiles.py`、`tools/trace_swi_consumers.py`、
`tools/trace_dma_consumers.py`。共用工具只負責 GDB remote protocol 與標準 GBA
memory/tile/OAM 操作；A5TJ 的 offset、來源判定與 negative evidence 均記在本目錄，
沒有套用其他遊戲的 ROM 格式假設。

## 下一個安全切片

先從一個可重複抵達的 UI／開場文字畫面建立本機原文表，再建立第一批 `work/*.jsonl`，以來源 hash、控制碼狀態、寬度預算與術語來源做審核。只有 decoder 能穩定重新抽出同一批資料、且回插後能 byte-for-byte 驗證，才進入有限量翻譯與 patch 工程。
