# 《勇者鬥惡龍怪獸篇 旅團之心》路線圖

## M0：基準與唯讀偵察

- [x] 建立遊戲專屬目錄、`game.yml`、README、工作帳本邊界。
- [x] 確認 GBA 標頭：`A9HJ`、Rev.00、`DQM-CARAVANH`、header complement。
- [x] 審核公開 clean ROM 指紋與目前本機候選的差異。
- [x] 建立不輸出完整原文的 `tools/recon_rom.py`。
- [x] 以獨立 GDB 埠在 clean A9HJ 驗證 mGBA ROM 入口、VRAM watchpoint 與開機 live layout；candidate 結果只作歷史對照。
- [x] 取得／核准 clean 日版 ROM，重新建立基準指紋。

## M1：文字與字型系統

目前進度（尚未完成 M1）：clean ROM 已證明文本 consumer、三層 script pointer selection、`0x92`／`0x93` 雙 byte glyph 合成、`E0`／`E1` alternate-glyph 消費、glyph writer 的 32／64-byte stride／DMA3 路徑與可達 menu tilemap；另已建立只使用未佔用 E1 slot 的手繪字形與固定 menu span encoder proof。codepage 完整 mapping、控制碼語義、字寬／VWF writer、所有 script 邊界與全量 round-trip 仍開放。

- [x] 收斂文本的目前儲存形式為 clean ROM 三層 pointer pool 指向 mixed-byte stream；`tools/audit_storage_form.py` 已重現 pointer／parser direct-read 證據，但 compression absence 與真正 record boundary 仍未證明。
- [x] 找到文本消費者、字型搬移與實際螢幕渲染路徑（clean `0x08012500`／`0x08013738`／`0x08013E00`／`0x08013E4C` 與 menu VRAM 已交叉驗證；`E0`／`E1` 指向 alternate pool `0x082E0BD4`）。
- [ ] 追蹤 title／menu／事件畫面，區分 tile、bitmap、sprite 與可能的 VWF 路徑。
- [ ] 確認指標／bank／壓縮格式與控制碼，不套用其他遊戲假設。
- [ ] 建立可重跑的 `research/*-decoded.jsonl` 本機原文表。
- [x] 以 clean pointer spans 統計 `FF`／缺少 `FF`／`FF` 後資料，保留 terminator 僅為候選而不誤切 script boundary。
- [x] 以三次／五次 A 的 clean mGBA/GDB trace 固定 title/logo → menu-like tilemap → text-parser 可達性；receipts 位於 `research/runtime-smoke-clean-three-inputs-20260817.md` 與 `research/runtime-smoke-clean-five-inputs-20260817.md`，未命中的 glyph／layout breakpoint 仍不視為 pass。
- [x] 分別記錄 glyph addressing 與 glyph identity 的證據層級（目前已完成一筆 38-token exact output round-trip；全遊戲 mapping 仍是後續工作）。
- [x] 固定 clean glyph writer／DMA3／layout 的可重跑靜態 receipt（完整 VWF 寬度與換行語義仍未完成）。
- [x] 固定 pair／single writer 的 output-slot `state+0x16` 每次 `+1` signatures，明確標記 clean fixed-cell 證據與 VWF 未證明邊界（`research/fixed-cell-vwf-risk-20260816.md`）。
- [x] 固定 `E0`／`E1` 一 byte look-ahead 與 alternate glyph pool 的 consumer receipt（索引到 Unicode 的 identity 仍未命名）。
- [x] 固定 `DF..FF` handler 的 source-parameter 消費形狀與 state-dependent read signatures（`tools/audit_control_consumption.py`；控制碼名稱、終止／換頁語義仍未完成）。
- [x] 以 clean code signatures 固定 parser outer-loop continuation、`F9` 兩分支匯合到固定一 byte read，以及 `FF` 的 state-dependent flag clearing；不把它們升格為 terminator／控制碼語義（`research/control-consumption-20260816.md`）。
- [x] 以 source-free aggregate receipt 盤點 clean code-unit 類別、pair 解出比例、alternate-glyph 使用 slots 與 control candidate 數量（`tools/audit_codepage_inventory.py`；未解 glyph identity 與控制碼語義仍未完成）。

## M2：帳本與有限翻譯

- [x] 建立 `translations/glossary.zh-TW.tsv`；遊戲標題已依 Wikipedia zh-tw／巴哈姆特／社群線索固定，UI 術語另保留批次上下文。
- [x] 以 clean menu block `g06:v00:m0000` 建立第一批本機 `work/*.jsonl` 與 source-free ledger；只覆蓋可驗證的固定 span，未宣稱全遊戲翻譯。
- [x] 在 bounded menu row 保留 `zh-Hans`／`zh-TW`、狀態、術語、控制碼與寬度預算；全量 rows 仍待完成。
- [x] 對 bounded menu work copy 以 `strip_translations.rb` 產生不含 `source` 的 ledger，並以 `cmp`／安全檢查驗證；全量 schema gate 仍待完成。
- [x] 以 clean `g06:v00:m0001` 固定 span 建立第二筆 source-free ledger，保留 `FE E4 23 FB FF` 動態尾段並完成 restore／strip／schema 檢查；全量 ledger 仍待完成。
- [x] 以 clean `g06:v00:m0006` 固定 span 建立第三筆 source-free ledger，保留 `FF` 尾段並完成 bounded restore／strip／schema 檢查；全量 ledger 仍待完成。
- [x] 以 clean `g06:v00:m0044` 固定 span 建立第四筆 source-free ledger，保留 `FF` 尾段並完成 bounded restore／strip／schema 檢查；全量 ledger 仍待完成。
- [x] 以 clean `g06:v00:m0045` 固定 span 建立第五筆 source-free ledger，保留 `FE`／`FF` 控制並完成 bounded restore／strip／schema 檢查；全量 ledger 仍待完成。
- [x] 以 clean `g06:v00:m0041` 固定 span 建立第六筆 source-free ledger，重用既有 E1 glyph、保留 `FF` 並完成 bounded restore／strip／schema 檢查；全量 ledger 仍待完成。
- [x] 以 clean `g06:v00:m0040` 固定 span 建立第七筆 source-free ledger，新增／重用 E1 glyph、保留 `FF` 並完成 bounded restore／strip／schema 檢查；全量 ledger 仍待完成。
- [x] 以 clean `g06:v00:m0042`／`m0043` 固定 span 建立第八批兩筆 source-free ledger，驗證 E0／E1 mixed-bank glyph、保留兩列 `FF` 並完成 bounded restore／strip／schema 檢查；全量 ledger 仍待完成。

## M3：回插與發布前 QA

- [x] 建立 bounded menu encoder／手繪 8x8 字庫與固定 span 回插器；全遊戲 encoder、字庫覆蓋與 relocation 仍待完成。
- [x] 對 `menu-batch-1` 完成 clean→patched bounded re-extraction 與 BPS apply round-trip；receipt 位於 `research/menu-batch-1-roundtrip-20260816.md`。
- [x] 對 `message-batch-2` 完成 clean→patched bounded re-extraction 與 BPS apply round-trip；receipt 位於 `research/message-batch-2-roundtrip-20260816.md`。
- [x] 對 `message-batch-3` 完成 clean→patched bounded re-extraction 與 BPS apply round-trip；receipt 位於 `research/message-batch-3-roundtrip-20260816.md`。
- [x] 對 `message-batch-4` 完成 clean→patched bounded re-extraction 與 BPS apply round-trip；receipt 位於 `research/message-batch-4-roundtrip-20260816.md`。
- [x] 對 `message-batch-5` 完成 clean→patched bounded re-extraction 與 BPS apply round-trip；receipt 位於 `research/message-batch-5-roundtrip-20260816.md`。
- [x] 對 `message-batch-6` 完成 clean→patched bounded re-extraction 與 BPS apply round-trip；receipt 位於 `research/message-batch-6-roundtrip-20260816.md`。
- [x] 對 `message-batch-7` 完成 clean→patched bounded re-extraction 與 BPS apply round-trip；receipt 位於 `research/message-batch-7-roundtrip-20260816.md`。
- [x] 對 `message-batch-8` 完成 clean→patched bounded re-extraction 與 BPS apply round-trip；receipt 位於 `research/message-batch-8-roundtrip-20260817.md`。
- [x] 將八個 bounded batch 以 disjoint-range merge 建立 cumulative ROM／BPS proof；receipt 位於 `research/bounded-batches-roundtrip-v8-20260817.md`，全遊戲 encoder／BPS 仍待完成。
- [x] 完成 clean extractor raw-span identity replay；receipt 位於 `research/raw-span-roundtrip-20260816.md`，只證明 byte-preserving replay，不替代 semantic encoder／完整 record boundary。
- [x] 以 pair／alternate／single／control token 重建 clean ROM bytes，完成 token-preserving encoder round-trip；receipt 位於 `research/token-encoder-roundtrip-20260817.md`，semantic encoder／完整 record boundary 仍待完成。
- [x] 對七批 cumulative patched ROM 完成有界 mGBA／GDB smoke trace；receipt 位於 `research/runtime-smoke-partial-20260816.md`，完整目標畫面／glyph／layout／全場景 QA 仍待完成。
- [ ] clean ROM → 重建 ROM → 重新抽取，確認未修改內容一致。
- [ ] 產生並套用 BPS，完成逐位元組 round-trip。
- [ ] 在 mGBA 及可用實機完成已覆蓋場景 QA，記錄未測畫面與剩餘風險。
