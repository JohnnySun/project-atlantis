# M1 bounded consumer evidence（2026-08-16）

這份紀錄把本回合的輸入、VRAM/OAM 與文字畫面證據分開保存；不包含 ROM、完整原文或任何二進位 dump。

## 執行條件

- 目標：日版 GBA A5TJ；ROM 只從本機合法候選讀取。
- emulator：已準備好的 mGBA 0.10.5 headless session，GDB port `2367`。
- 本回合沒有再編譯或修改 mGBA，也沒有修改 ROM。
- GDB 協定 client 沿用專案既有的通用 `games/shining-soul-1/tools/gdbstub_client.py`；OAM 合成沿用 `games/shining-soul-1/tools/render_oam_composite.py`。兩者只處理 GDB remote protocol 與標準 GBA memory/tile/OAM，不讀取或假設《光明之魂 1》的 ROM 資料格式。

## 輸入證據

1. 連線後在 `0x04000130` 設定 `Z3,4000130,2`。
2. 連續命中 PC `0x080a9a0a`；該點前一條指令由 KEYINPUT 讀取 halfword。
3. GBA active-low 值：idle `0x3ff`、A `0x3fe`、Start `0x3f7`。
4. 在 stop 後覆寫輸入目的暫存器，維持 Start 多個 poll 再釋放；畫面從 logo 狀態轉換到另一個 OAM/VRAM 狀態。

因此這一段是「遊戲實際讀取輸入並產生狀態轉換」的證據，不是向 ROM 寫入按鍵資料。

## VRAM/OAM 證據

Start 後的 dump 統計為：VRAM 非零 4,226 bytes、palette 非零 61 bytes、OAM 非零 311 bytes；logo/idle 對照為 3,192、289、128。Start 後 OAM entries 0–45 為 46 個可合成 sprite，`DISPCNT=0x7f00`，OBJ tile base 為 `0x10000`。

依 OAM 的 x/y、shape/size、tile index、palette bank、翻轉旗標合成，並使用 GBA 4bpp、8×8 tile、OBJ 1D mapping；不能把 OBJ tile 以單純順序格狀排列代替 OAM 合成。

## 文字消費者證據

以 OBJ palette RAM 的 OBJ slice 和 OAM/VRAM dump 執行既有 renderer 後，畫面得到三行遊戲內日文免責文字。這確認文字圖像已進入 OBJ tile → palette → OAM → frame 的消費路徑；本證據不等同於已解出 source table、字元代碼或 codepage。

對 `0x06010000` 設 `Z2,6010000,4` 的 20 秒 bounded write-watchpoint 收到 `OK` 但沒有 stop。故目前不宣稱 CPU/DMA 的搬移 PC、ROM source offset、壓縮格式或控制碼；這是下一個工程切片的明確負面結果。

## 重跑時的人工驗收

- 輸入 watchpoint 必須在固定的 KEYINPUT consumer PC 命中，且 active-low Start 後 OAM/VRAM 統計產生可辨識差異。
- OAM composite 必須使用 OBJ palette slice；直接把完整 512-entry palette 當成 BG-only 256-entry 輸入會得到全黑假陰性。
- 渲染結果只用來證明畫面消費者，不得直接把畫面 OCR 或肉眼讀字當成可提交的原文表。
