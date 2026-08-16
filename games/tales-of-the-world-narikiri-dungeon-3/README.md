# 《世界傳說：換裝迷宮 3》漢化工作區

本目錄只處理日版 GBA《Tales of the World: Narikiri Dungeon 3》（B3TJ）的
zh-TW 研究與本地化。ROM、存檔、完整日文原文表、解碼輸出與實驗產物都留在
本機，不進 Git；可提交的是偵察結論、可重跑工具、測試與不含原文的工作文件。

## 目前狀態

目前完成 M0 身分鎖定、M1 工程可行性偵察、M1.5 與 M1.6 的 bounded consumer 回合：已
確認一批以 NUL 結尾的標準 Shift-JIS 候選資料、可重現的嚴格抽取邊界、五窗
absolute／relative 指標分層，以及遊戲啟動期實際執行的 BIOS 圖形解壓縮路徑。
M1.5 已確認早期 KEYINPUT polling caller，但選定 record 的 read watchpoint 在
bounded menu 序列中為 negative。M1.6 已確認 `0x08003444` 會被真實 UI／資源
載入路徑呼叫，但本回合的 8 個 resolved pointers 全部在五個文字窗外；selected
record `0x08146EE0` read watchpoint 仍為 negative。**尚未開始翻譯，也尚未證明
文字 renderer、字型 codepage 或可逆回插。** 不把既有英文 patch 的少量選單／開頭
內容當作完整翻譯來源。

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
- 尚無 builder、容量檢查、checksum/round-trip 或實機／mGBA 回插驗證；目前
  不可宣稱能安全擴長字串。第一個回插試驗必須先限制在等長或已證明有餘裕的
  NUL 記錄，並逐筆保存原始 bytes、控制碼與 renderer 結果。
- 本次只完成有限 runtime 證據；輸入導覽、事件／戰鬥畫面和文字畫面尚未被
  可靠導航到，因此沒有把「未命中」解讀成「不存在」。

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

## 外部工程參考

[Kajitani-Eizan 的舊專案頁](https://www.blade2187.com/projects/narikiri-dungeon-3/)
只作為「曾有 v1.11、偏選單／開頭的部分 patch」工程背景；它不是本專案的完整
翻譯來源，也不替代本 ROM 的格式驗證。
