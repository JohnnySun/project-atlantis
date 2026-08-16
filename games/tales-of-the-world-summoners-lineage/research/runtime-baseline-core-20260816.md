# A9PJ M1 共用 core/gba runtime baseline（2026-08-16）

本紀錄使用 main 上的共用 runtime 工具（commit `0455796`），不在本遊戲重寫 GDB
packet、VRAM dump 或 renderer。原始 ROM、mGBA 暫存 build、GDB session、raw RAM／VRAM
dump 與 PPM／PNG 都留在 `/private/tmp`，不進 Git。

## 範圍與重現

- ROM：A9PJ clean dump，SHA-256
  `b41c293fc0ed6111b7a37d960d9cd0c685e5d521a4739e0e2eaa7ff6186cfdd3`。
- mGBA：既有 `/private/tmp` 暫存 binary，命令列載入同一份 A9PJ；沒有修改或重建。
- listener：本 session 獨立 `127.0.0.1:23901`；每次只建立一條 GDB connection，完成
  後停止已核對的 mGBA PID。
- capture：`core/gba/capture_runtime.py`，只做 continue／interrupt 與唯讀記憶體讀取，
  沒有寫入 ROM、RAM 或寄存器。

```sh
PYTHONDONTWRITEBYTECODE=1 python3 core/gba/capture_runtime.py \
  --port 23901 --run-seconds 1 \
  --dump-dir /private/tmp/tow-a9pj-core-runtime-20260816 \
  --output /private/tmp/tow-a9pj-core-runtime-20260816/summary.json

PYTHONDONTWRITEBYTECODE=1 python3 core/gba/capture_runtime.py \
  --port 23901 --run-seconds 5 \
  --dump-dir /private/tmp/tow-a9pj-core-runtime-5s-20260816 \
  --output /private/tmp/tow-a9pj-core-runtime-5s-20260816/summary.json
```

兩次摘要均為 `initial_stop=S02`、`runtime_stop=S02`，GDB stub 回報
`qSupported` 的 standard feature set。capture 後 `23901` listener 已清除；其他遊戲
的 mGBA／port 未觸碰。

## 1 秒 startup frame

共用 capture 讀到：

| register | 值 |
| --- | --- |
| `DISPCNT` | `0x0200` |
| `BG0CNT` | `0x0000` |
| `BG1CNT` | `0x0105` |
| `BG2CNT` | `0x0000` |
| `BG3CNT` | `0x0000` |
| runtime PC | `0x03002004`（IWRAM） |

`DISPCNT=0x0200` 只開啟 BG1；`BG1CNT=0x0105` 解析為 4bpp、charblock `0x4000`、
screenblock `0x0800`。使用 `core/gba/render_vram.py --mode tilemap` 以這組參數重建後，
得到可辨識的 Namco startup logo，證明本遊戲的 BG charblock／screenblock 與 GBA 4bpp
nibble 順序可由共用 renderer 正確解讀。

該畫面使用的 77 個 tile ID 中有 76 個非零；只有 3 個非零 tile ID 能在 clean ROM
找到完全相同的 32-byte run（其餘可能是解壓／搬移後資料）。這是 graphics data 的
byte-match 線索，不是文字或字型證據。

1 秒 raw region hash（只作本機 receipt）：

| region | non-zero bytes | SHA-256 |
| --- | ---: | --- |
| VRAM | 2,852 / 98,304 | `7be0bd8eb98545a0f5d48810dbeabe7e512aec7742eed628fc17b04a042c2628` |
| palette | 39 / 1,024 | `45430019b4e6456c8a636612cf298263853cf0153da7c061d8422d3bc21225a7` |
| OAM | 0 / 1,024 | `5f70bf18a086007016e948b04aed3b82103a36bea41755b6cddfaf10ace3c6ef` |

## 5 秒 startup／演出 frame

5 秒後讀到：

| register | 值 |
| --- | --- |
| `DISPCNT` | `0x1F40` |
| `BG0CNT` | `0x0000` |
| `BG1CNT` | `0x0105` |
| `BG2CNT` | `0x020A` |
| `BG3CNT` | `0x830E` |
| runtime PC | `0x03002024`（IWRAM） |

此時所有 BG 與 OBJ layer 已開啟，OBJ mapping bit 為 1D。用共用
`render_vram.py` 分別以 BG2 `charbase=0x8000/screenbase=0x1000`、BG3
`charbase=0xC000/screenbase=0x1800` 重建，可看到兩個角色／演出圖層；BG1 是局部效果
tile。共用 `render_oam.py --mapping 1d` 讀到 256 個非零 OAM bytes，但當下沒有可見
sprite 被合成，故不能把 OAM bytes 當成文字 tile。

5 秒 raw region hash：

| region | non-zero bytes | SHA-256 |
| --- | ---: | --- |
| VRAM | 8,088 / 98,304 | `e3ad8be1e2db49b5cc7c1a622b788974c7eca40042cbb93a07d7ce7c7e4e985e` |
| palette | 120 / 1,024 | `df5953b3361dbeb9f5e307727f02799c86f63711e797f8a99a393d7f06083582` |
| OAM | 256 / 1,024 | `d39570ac8574cbe40a6902528d0515dc88217c59256be6154fa16d30b5d9a98d` |

## 證據判定

| 項目 | 狀態 | 可宣稱內容 |
| --- | --- | --- |
| GBA display mode／BG register interpretation | `confirmed-runtime` | A9PJ 的實際 BG1／BG2／BG3 layer 可由共用 renderer 重建 |
| startup graphics path | `confirmed-runtime` | startup logo 與演出角色圖層確實進入 VRAM／tilemap |
| 事件／選單文字 consumer | `not-confirmed` | 兩次 baseline 都沒有取得文字畫面、PC call site 或 source pointer |
| codepage／控制碼 | `not-confirmed` | graphics byte-match 與 layer render 不提供 code unit identity |
| 日文 source table | `blocked` | 沒有新增任何可安全建立的 `string_id`／source row |
| zh-TW work ledger | `empty-by-design` | 未開始翻譯，不產生猜測 source hash 或 ledger row |

因此本次只把「graphics path confirmed」加入 M1 證據矩陣；不把 Namco logo、角色圖層或
任意 tilemap entry 當作日文文本。下一個文字里程碑仍需遊戲專屬的 static control-flow／
pointer 分析或另有明確授權的可達文字畫面證據。
