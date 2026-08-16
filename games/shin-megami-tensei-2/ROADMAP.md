# 《真・女神轉生 II》路線圖

## M0：身分、範圍與唯讀基準

- [x] 建立獨立 slug `games/shin-megami-tensei-2/`，不混入其他遊戲資料。
- [x] 記錄 A5TJ header、ROM size、CRC32、MD5、SHA-256 與 header complement 差異；不修補原 ROM。
- [x] 建立不輸出完整原文的 `tools/recon_static.py`。
- [x] 使用本 session 專用的 2367 headless GDB 做一次有界輸入／VRAM／OAM 回合。
- [x] 依 GBA 標準 VRAM、OBJ palette、OAM 與 4bpp/1D mapping 假設完成畫面級交叉驗證：Start 後可渲染出遊戲內日文免責文字。

## M1：文字消費者與格式偵察

- [x] 以 `Z3,04000130,2` 讀取 watchpoint 確認 KEYINPUT 的執行期消費點（PC `0x080a9a0a`），並以 active-low 值完成一次 Start 狀態轉換。
- [x] 記錄新畫面的 `DISPCNT`、BG 設定、VRAM/OAM 非零統計、OBJ tile 範圍與 46 個 active sprite 的可重現證據。
- [x] 確認至少一個實際文字消費結果：OBJ sprite 合成影像中出現三行日文免責文字。
- [~] 找到文字的實際儲存形式、字元代碼與 codepage；目前只有畫面消費證據，沒有把影像反推成原文表。
- [ ] 確認字串池／指標／bank、壓縮、換行與控制碼；不套用 SMT I、黃金太陽或其他遊戲格式。
- [ ] 分別定位惡魔、技能、道具、系統與劇情資料，並建立本作 decoder 及本機 `research/*-decoded.jsonl`。
- [ ] 以未修改資料重新抽取驗證可逆回插路徑。

## M1.5：OBJ 字型來源有界分析

- [x] 使用 `core/gba/` 工具和本作 bounded analyzer 重現 Start 後畫面，解析 46 個 active OAM sprite、84 個 unique 4bpp/1D OBJ tile，保留位置、tile index、hash 與計數，不提交 raw dump。
- [x] 對 ROM 做完整 2×2 sprite glyph exact search，以及 hflip/vflip/rotate180/nibble-swap 的有界變形 search；完整 glyph 命中為 0，沒有候選 font base/stride。
- [x] 把 IWRAM、有效分塊讀取的完整 EWRAM、固定 OAM source 與 ROM 分開比對；IWRAM/EWRAM 都沒有完整 sprite glyph 命中，零 tile match 另列為反例。
- [x] 以 4-byte 對齊、bounded output/candidate 的標準 GBA LZ77/RL scan 檢查完整 glyph；valid stream 中沒有命中，不能因此宣稱文字已壓縮格式化。
- [x] 確認一條較早的 OAM consumer：IWRAM `0x030033f0` 的 OAM buffer 由 DMA3 搬到 `0x07000000`；這是 OAM source 證據，不等於 OBJ glyph source。
- [x] 固定 OBJ-DMA routine（file `0x0baecc`，source `0x02001000`、destination `0x06013000`、control `0x84000700`）已在 M1.6 完成 entry／literal-pool／ARM7TDMI 邊界驗證；runtime 是否命中另行列在 M1.6。
- [~] M1.5 的結果是「來源範圍已縮小但尚未建立 source table」；因此 codepage、stable string ID、控制碼與翻譯仍保持封鎖。

## M1.6：固定 DMA、transfer queue 與 staging writer 有界追蹤

- [x] 完整驗證 `0x080baecc`：9 條 Thumb 指令、最後 `BX LR` 在 `0x080baedc`、alignment padding 後 literal pool `0x080baee0`–`0x080baef0`；`source=0x02001000`、`destination=0x06013000`、`CNT=0x84000700` 均由固定 literals 組裝，沒有 direct BL caller。
- [x] 驗證另外七個 `0x06013000` fixed-DMA copies。routine entry 為 `0x080bb318`、`0x080bb61c`、`0x080bbcd8`、`0x080bc584`、`0x080bc978`、`0x080d8d80`、`0x080d9448`；其中後五個 M1.5 site 名稱是第一條 source `STR`，不再混稱函式 entry。
- [x] 反組譯並記錄通用 queue drain／producer：`0x080ad01c`／`0x080ad0fc`，64 entries，base `0x02009004`、stride `0x64`，source field `+0x14`，callback table `0x0815eeec`，dynamic dispatch sites `0x080ad070`／`0x080ad0a2`／`0x080ad0be`。bounded code path 沒有獨立 head/tail slot；entry state `+0x00` 是實際 consumed state。
- [x] Formal probe 從 reset arm staging、queue entries 與 DMA3 SAD/DAD/CNT watches，並以 `core/gba/gdbstub_client.py` 重現 Start：35 秒、220 stop bound、6 次 KEYINPUT read、Start sent；queue producer 2 hits、dispatch 30 hits、LZ77 wrapper 1 hit，queue entries `0x02009068`／`0x020090cc` 各自帶有兩個已記錄 ROM source pointers。
- [x] 陰性窗口已界定：八個固定 OBJ-DMA site 0 hit、`0x080baef0` 0 hit、`0x02001000` staging write 0 hit；DMA3 metadata watch 有 hit，但 formal report 的唯一 LZ77 destination 是 `0x0200f874`，不是 `0x02001000` 或 OBJ VRAM。這不否定別的狀態／轉場，僅否定本次 reset→Start window。
- [~] 尚未建立 glyph source/staging → transform → OBJ VRAM → OAM 的因果鏈；`0x080baef0` 仍是 staging candidate，附近 `0x081869c8` descriptor table（含 `0x080baef1` Thumb pointer）是下一個最小 indirect-dispatch 追蹤點。不得以 queue resource pointers 或畫面 OCR 代替 source table。
- [ ] 取得實際 glyph writer 的 ROM pointer／RAM table／code-unit argument；確認 1–3 個重複 glyph 的 source hash、transform 與 OBJ tile hash 後，才可開始建立 stable string ID、codepage 或翻譯批次。

## M2：可審核翻譯 ledger

- [ ] 先完成日文 source table 與 stable string ID，再建立第一個有限 UI／事件批次。
- [ ] 專有名詞先查 Wikipedia zh-tw、巴哈姆特及其他獨立社群來源，建立 `zh-TW` 術語表與來源紀錄。
- [ ] 以 `restore_translations.rb` 產生本機工作記錄，保留來源 hash、控制碼與寬度預算。
- [ ] 以 `strip_translations.rb` 產生不含 `source` 的提交 ledger，通過 schema 與 repository safety 檢查。

## M3：回插與 QA

- [ ] 建立本作專用 encoder、字庫與回插器。
- [ ] clean ROM → 重建 ROM → 重新抽取，確認未修改內容一致。
- [ ] 產生／套用 BPS 並完成 byte-for-byte round trip。
- [ ] 在 mGBA 驗證已翻譯場景；未測畫面、字寬、控制碼與存檔風險都要明列。
