# 《光明之魂》（シャイニング・ソウル）漢化工作區

本目錄用於從乾淨日版 ROM 建立可重現的簡體／繁體本地化流程。ROM、抽出的原文、渲染出的字形圖片及實驗構建只保存在本機，不進入 Git；本遊戲使用 `docs/TRANSLATION-LEDGER.md` 定義的帳本方案（`core/ledger/strip_translations.rb`／`restore_translations.rb`），**不採用**兩款黃金太陽既有的「工作記錄直接進 Git」格式。

這是新版 `gba-localization` skill（`.agents/skills/gba-localization/SKILL.md`）第一次在全新遊戲上實際使用，本檔案同時記錄偵察發現與該 skill 使用心得（見下方「skill 使用備註」）。

## 當前進度（第二輪偵察後：字型格式與部分字形資料位置已確認，文字系統仍未完全解出）

第二輪偵察新增 `capstone`（ARM/THUMB 反組譯）與 `mgba --gdb`（即時記憶體觀察）兩項工具，取得第一輪純靜態掃描做不到的正面結果，見下方「第二輪偵察」一節。第一輪的负面結果（見下）仍然有效，未被推翻。

- **ROM 身分已確認**：`file`／自製標頭解析器讀出卡匣標頭 `SHINING SOUL`／game code `AHUJ`／maker code `8P`，標頭補數校驗（0xBD）計算值與 ROM 內實際值一致（`0x2e`），確認標頭未損壞。檔案大小 8,388,608 bytes（8 MiB＝64 Mbit），與目錄檔名「64Mb」宣告一致。
- **雜湊已計算**（未與任何外部資料庫比對，只是本機記錄）：見下表。
- **ROM 實際使用範圍**：以 16 KiB 區塊掃描 Shannon entropy，`0x660000` 之後到檔案結尾（`0x800000`）全部是 `0xFF` 填充，代表卡帶實際內容只佔約 6.7 MiB，其餘是空白容量。
- **文字系統尚未解出**——這是本輪最重要的負面結果，記錄如下，避免下次重工：
  - 對整個 ROM 做「哪些位元組序列本身是合法 Shift-JIS」的結構掃描，命中大量長片段，但人工檢視後幾乎全部是圖形／調色盤／音效等二進位資料湊巧滿足 Shift-JIS 前後導位元組規則的假陽性（重複同一兩三個「字」、字符多樣性低、且落在熵分析判定的圖形資料區間內），不是對話文字。
  - 對常見日文 UI／戰鬥詞彙（`はい`、`いいえ`、`レベル`、`たたかう`、`にげる`、`どうぐ`、`セーブ`、`ロード`、`コマンド`等，含半形／全形變體）逐一以其標準 Shift-JIS 位元組序列在整個 ROM 內搜尋精確匹配，**全部找不到**。這代表文字很可能不是以未壓縮的標準 Shift-JIS 直接存放，而是像黃金太陽一樣走自訂編碼（壓縮、自訂 codepage、或兩者皆有），但目前無法進一步判斷是哪一種——Sega 的自製文字系統目前沒有找到任何公開的逆向工程紀錄可以參考（見下方「外部資料」）。
  - 未找到明確的字串指標表：以「連續多個 4-byte LE 值都落在 `0x08000000`–`0x087FFFFF` ROM 位址空間內」為訊號掃描全ROM，命中的候選全部集中在 `0x000000`–`0x054000`（推測是程式碼區，很可能是 switch-case 跳轉表或字面量池），沒有在較大範圍內找到典型「字串表」形狀（大量、位址遞增、分佈在資料區而非程式碼區）的候選。
  - BIOS 解壓縮呼叫（THUMB `swi` 指令，半字組對齊掃描）確認 ROM 程式碼裡有呼叫 `LZ77UnCompWram`(11次)／`LZ77UnCompVram`(28次)／`HuffUnComp`(15次)／`RLUnCompWram`(16次)／`RLUnCompVram`(10次) 等 BIOS 服務，但這只證明「這些 BIOS 常式有被呼叫」，**不能**證明文字資料走哪一種、甚至是否被這些常式處理——GBA 遊戲用 BIOS LZ77／RLE 壓縮圖形資源非常普遍，這批呼叫點極可能主要服務圖形／音效資料。且此掃描本身有大量假陽性（原始逐位元組掃描曾一度數到 85 次 `LZ77UnCompVram` 候選，改成半字組對齊掃描後降到 28 次，仍未反組譯驗證是否為真指令）。
  - 原始的「壓縮簽章」（magic byte 0x10／0x24／0x30 加合理大小欄位）字組對齊全域掃描噪音極大（LZ77 候選 11,455 個、Huffman 候選 2,298 個、RLE 候選 3,022 個），單獨看毫無意義，只有在能交叉比對「真的被程式碼位址引用」時才有價值——這一步本輪沒有做（需要反組譯，超出第一輪唯讀偵察範圍）。
- **外部資料**：搜尋 romhacking.net、GBAtemp、Shining Force Library 等社群站台，沒有找到任何公開的《光明之魂》（GBA，SS1／SS2）文字格式逆向工程筆記；GBAtemp 上一篇 Shining Soul II 的 ROM hacking 部落格只是宣布專案開始，未含技術細節。目前判斷本作文字系統需要從零開始逆向，沒有現成參考可以站在肩膀上。

## 第二輪偵察（capstone 反組譯 + mGBA GDB 即時記憶體觀察）

工具環境：`capstone` 5.0.x 只裝在 `/usr/bin/python3`（Command Line Tools 版本），**不是** `/opt/homebrew/bin/python3`——之後重跑本節腳本務必用前者，否則會 `ModuleNotFoundError`。`mgba`（`/opt/homebrew/bin/mgba`，0.10.5）用 `-g` 開 GDB remote server（預設埠 2345）；本機沒有 `gdb`，改用 `games/shining-soul-1/tools/gdbstub_client.py`（純 Python、只實作本次需要的封包型別）直接對埠 2345 說 GDB remote serial protocol，`lldb` 完全沒試（`gdbstub_client.py` 一寫成功就直接堪用，未比較 lldb 路線）。本機沒有、也沒有另外取得任何 GBA BIOS dump，全程用 mGBA 內建 HLE BIOS 開機，未使用任何未授權的 Nintendo BIOS 檔案。

### 反組譯結果：BIOS 解壓縮呼叫候選全部無法確認為真指令（強化版負面結果）

`games/shining-soul-1/tools/disasm_swi_calls.py`（新增）對第一輪 `scan_swi_calls.py --align2` 找到的每個 `swi 0x10`–`0x18`（BitUnPack／LZ77／HuffUnComp／RLUnComp／Diff8bit／Diff16bit）候選位址，往回找最近的 THUMB `push {..,lr}` 當函式起點錨點，用 capstone 正向反組譯到候選位址，檢查是否乾淨落在一個 `svc` 指令上。

結果：137 個候選中，128 個「未對齊或不是 svc」、11 個「無法解碼」、只有 **9 個**「乾淨落在 svc 上」。但人工檢視這 9 個的反組譯結果後判斷**沒有一個是真指令**——往回展開的所謂「函式」裡出現大量在 ARM7TDMI（GBA CPU）上根本不存在的指令（例如 `bxns`〔ARMv8-M 專屬〕、`mrrc`／`cdp2`／`stc2`〔ARM 協處理器指令，GBA 沒有協處理器〕），以及跳到 ROM 範圍外或明顯不合理位址的分支。這代表 THUMB 的密集編碼空間（幾乎任何 16-bit pattern 都能解碼成某個合法指令）讓「反組譯不出錯」本身是很弱的判準——這批位元組其實落在圖形／資料區，只是湊巧被解碼成語法合法但語意荒謬的指令序列。**結論：第一輪找到的全部 137 個 BIOS 壓縮呼叫候選，經反組譯覆核後沒有一個能確認是真的、會被執行到的呼叫點**；連帶地，「文字資料經 BIOS LZ77／Huffman／RLE 壓縮」這個假說目前完全沒有直接證據支持（也沒有被排除——只是這條路線用簡單反組譯走不通，需要從進入點做完整的遞迴控制流重建才有機會分辨程式碼與資料，這超出本輪範圍）。

腳本本身的方法論限制寫在 docstring 裡（錨點探測是啟發式、暫存器回溯只認得 `mov`／`ldr [pc,#n]` 的簡單情形），可重跑：

```sh
/usr/bin/python3 games/shining-soul-1/tools/disasm_swi_calls.py \
  games/shining-soul-1/roms/base/Shining_Soul_JP_AHUJ8P.gba
```

### mGBA GDB 即時記憶體觀察：確認畫面渲染、字型格式、部分字形資料的 ROM 位置

流程：`mgba -g <rom>` 背景啟動（無視窗環境下 `screencapture` 回報 `could not create image from display`，代表這台機器沒有可用的螢幕/顯示 session，無法直接截 mGBA 視窗——因此改用 GDB 連線讀記憶體、自己解碼 VRAM 內容並渲染成 PPM/PNG 圖片來做視覺核對，而不是依賴螢幕截圖），`gdbstub_client.py` 連線後 `c`（continue）＋計時＋`\x03`（interrupt）交替，讀 I/O 暫存器（`DISPCNT`／`BGxCNT`）、VRAM（`0x06000000`，96 KiB）、OAM（`0x07000000`）、調色盤（`0x05000000`）。

**重要操作細節（供下次重跑參考，避免重踩坑）**：
- mGBA 的 GDB stub 一個連線失效後**不會**乾淨接受下一個新連線（`connect()` 會逾時掛住）——每次要重連都必須先 `pkill` 掉舊的 mgba 行程、重開一個新的，而不是重用同一個埠。
- 就算同一條連線內，兩個封包**緊接著送**（沒有間隔）有一定機率讓 stub 沒回應（`_read_packet` 逾時）——`gdbstub_client.py` 的 `send()` 已加上送出前 50ms 延遲＋逾時重試一次，加了之後穩定。這代表本節所有結果都是在單一條連線、全程不中斷的情況下跑出來的。

**跑到的畫面**：開機後 run 約 10–30 秒（未按任何鍵），`DISPCNT=0x1240`（mode 0，BG1＋OBJ 啟用，OBJ 1D mapping），VRAM 內容在幾個固定畫面間循環（推測是 title 畫面的雲層背景動畫迴圈，OAM／調色盤在此期間完全不變），判斷此時已到達**標題畫面**（logo＋著作權年份＋按鍵提示），尚未進一步往下（見「未解決」）。

- ✅ **已確認**：BG1（`charbase=0x6000000`／`screenbase=0x600e800`／4bpp）的完整 32×32 tilemap，用本輪新增的 `games/shining-soul-1/tools/render_vram_tiles.py` 依調色盤（`0x05000000`）解碼渲染成圖片，畫面**直接是「SHINING SOUL」標題 logo＋雲層背景＋「©SEGA 2002」**（見 `research/title-screen-bg1-render.png`，已存檔）——這是本專案第一次拿到「渲染出的畫面內容與已知遊戲外觀吻合」等級的證據，不再只是位元組層級推測。
- ✅ **已確認**：GBA 4bpp、8×8px、32 bytes/tile 的標準 tile 格式假設正確——如果格式假設錯誤，解碼出來的會是雜訊而不是可辨識的 logo 圖案；渲染結果的清晰度本身就是格式正確性的證據。
- ✅ **已確認**：OAM（`0x07000000`）目前有 6 個啟用的 sprite（shape=1／size=2＝32×16px＝4×2 tiles，OBJ 1D mapping，palette bank 14），tile 編號 0/8/16/24/32/40，依 OAM 的實際 x/y/tile 排列（而非單純循序畫格子）正確合成後，畫面是**「シャイニング・ソウル」（片假名）在上、「PUSH START」（拉丁字母）在下**（見 `research/title-screen-push-start-obj-render.png`）——這是本輪唯一一處「看到疑似字型資料，且經視覺核對確認真的是文字（片假名＋拉丁字母混排）」的證據，不是猜測。
  - **重要教訓（已修正的錯誤路線）**：分析初期曾把 VRAM offset `0xE800`–`0xF800` 這段資料當成 charblock 裡的一般 tile 像素資料，粗略渲染後主觀覺得像一張完整 ASCII 字母表加片假名表，一度以為找到了整個字型系統。後來核對 GBA VRAM 版面配置才發現：`0x6000000`–`0x6010000`（charblock 0–3）中，screenblock 28–31（也就是位元組 offset `0xE000`–`0x10000`）依照 BG0／BG1 目前的 `screenbase` 設定，其實是**畫面／tilemap 資料**（16-bit 的 tile 編號＋翻轉旗標＋調色盤欄位），不是原始像素——把結構化、遞增的 tilemap entry 位元組硬解成 4bpp 像素，剛好因為數值規律而長得像「有規律的方塊圖案」，在縮圖尺度下誤判成文字表。這不是真的字型資料，該「發現」已撤回。教訓：**先核對 VRAM offset 落在 charblock（tile 像素資料）還是 screenblock（tilemap）範圍，再決定怎麼解碼**——`render_vram_tiles.py` 的 docstring 已記錄這個區分，供下次直接照做。
  - 真正查到片假名＋拉丁字母的，是 OBJ tile 區（`0x6010000`–`0x6018000`，這段沒有 screenblock 混用問題，恆為像素資料），且是用 OAM 的實際 sprite 排列（而非單純方格）合成才第一次看對，純方格排列（`--cols 8`）合成的中間結果其實是破碎、看不太懂的「PUS.. H ST.. HK1」——這也記錄下來，提醒**渲染 OBJ tile 資料一定要照 OAM 的實際擺放方式合成，單純按 tile 編號順序排格子會把字元拆散、误导判斷**。
- ✅ **已確認**（ROM 來源，部分）：組成「シャイニング・ソウル／PUSH START」畫面的 48 個 OBJ tile（VRAM `0x6010000`–`0x6010600`）逐格在 ROM 內做精確位元組搜尋，40/48 格（扣除 5 格全零、3 格疑似落在無關資料區的假陽性短匹配）在 ROM `0x62AA44`–`0x62B8E4`（約 3.7 KiB 範圍內，非完全連續）**找到逐位元組相同的原始拷貝**，且觀察到重複字元（如兩個「S」）在 ROM 裡對應**同一個**來源 tile、於執行期被複製到 VRAM 兩個不同位置——這是「每個字元一份共用原始字形、依需要拷貝到畫面對應位置」這種正常字型系統的典型特徵，不是逐畫面各自畫一張獨立點陣圖。**這批 tile 資料是逐位元組原封不動被拷貝進 VRAM，沒有經過 LZ77／Huffman／RLE 解壓縮**（若經壓縮，VRAM 內容不會與 ROM 內容逐位元組相同）——這與本節「BIOS 壓縮呼叫候選全部無法確認」的反組譯負面結果方向一致（至少這批資料確定不是靠 BIOS 解壓縮常式產生的）。
  - **尚未找到**：是哪段程式碼把 ROM `0x62AA44` 附近資料搬進 VRAM `0x6010000`——在 ROM 全域搜尋「word-aligned 4-byte LE 值落在 `0x0862A000`–`0x0862C000`」找不到任何命中，代表載入常式不是靠簡單的絕對位址常數池指標（可能是 halfword 對齊、runtime 加法算出、或透過某種索引表間接引用）；也還沒有找到「哪個位元組＝哪個字元代碼」的對照表（codepage），只確認了字形圖案本身存在、位置、格式。
- ⚠️ **未解決／不確定**：嘗試用 `gdbstub_client.py` 的 `write_mem` 直接寫 `KEYINPUT`（`0x04000130`）模擬按下 START／A 鍵（十次短暫 continue＋改寫交替，希望撐過按鍵邊緣觸發判定），想借此跳過標題畫面進入選單／對話等真正需要文字系統渲染任意字串的畫面，但畫面（`DISPCNT`、VRAM hash 循環模式）在模擬按鍵前後完全沒有變化。無法判斷是（a）mGBA 每畫格都用真實主機輸入狀態覆寫掉這個位址、我們的寫入根本沒撐過一個畫格，還是（b）此時遊戲邏輯本來就還不接受輸入（例如固定長度的不可跳過開場動畫尚未跑完），還是（c）其他原因。**這是本輪最大的未竟事項**——目前只確認了標題畫面的靜態字形資料，還沒有拿到任何「同一批字形 tile 被組成第二種、不同的字串」這種更強的「這是可重用字型」證據（雖然「シャイニング・ソウル／PUSH START」內部已有重複字元共用來源 tile 的證據，一定程度上支持是真字型而非純美術點陣圖，但只看過一組字串仍嫌單薄）。

以上三支新工具（`disasm_swi_calls.py`、`gdbstub_client.py`、`render_vram_tiles.py`）都在 `games/shining-soul-1/tools/`，全部唯讀（`gdbstub_client.py` 的 `write_mem` 是唯一寫入操作，只寫模擬器的執行期記憶體，不寫 ROM 檔案本身）。

## 第三輪偵察（跳過標題畫面成功；找到字型載入路徑但未找到 codepage）

工具環境同第二輪（`mgba` 0.10.5、`/usr/bin/python3` 的 capstone、`gdbstub_client.py`）。本輪對 `games/shining-soul-1/tools/gdbstub_client.py` 新增了 watchpoint（`Z`/`z` 封包，讀/寫/讀寫三種）、暫存器寫入（`P` 封包）、以及會阻塞等待非同步 stop-reply 的 `cont_and_wait()`，取代單純的「寫記憶體＋短暫 continue／interrupt 交替」。這批協定細節（欄位格式、成功／不支援的回應）是直接對照 mGBA 0.10.5 原始碼 `src/debugger/gdb-stub.c` 核對過的，不是從通用 GDB remote protocol 文件猜的——mGBA 的 stub 是部分實作，值得下次直接看程式碼再用。

### 根因確認：直接寫 `KEYINPUT` 為什麼從第一輪就注定無效

對照 mGBA 0.10.5 原始碼 `src/gba/io.c`（已核對，非 `master` 分支臆測）`GBAIORead()` 函式的 `REG_KEYINPUT` case：

```c
case REG_KEYINPUT: {
    ...
    if (gba->keyCallback) {
        gba->keysActive = gba->keyCallback->readKeys(gba->keyCallback);
        ...
    }
    uint16_t input = gba->keysActive;
    ...
    gba->memory.io[address >> 1] = 0x3FF ^ input;
}
```

這段程式碼在**每一次**遊戲程式碼讀取 `KEYINPUT` 時都會重新執行，把 `gba->keysActive`（來自實際主機輸入來源，這台無顯示 session 的機器上恆為「無按鍵」）重新寫回 `gba->memory.io[]`。也就是說，`gdbstub_client.py` 的 `write_mem` 對 `KEYINPUT` 位址的任何寫入，都會在遊戲程式碼下一次讀取該暫存器時被無條件覆寫——這不是時間掌握或位元極性的問題（上一輪懷疑的方向），而是**架構性地不可能透過記憶體寫入模擬按鍵**：GDB 的 `m`/`M` 封包只能碰到 `gba->memory.io[]` 這個「快取」，碰不到真正決定其值的 `gba->keysActive`／`keyCallback`（那是模拟器行程自己的 C 結構欄位，不在 GBA 位址空間裡，GDB stub 的目標記憶體空間也搆不到）。這個結論已對照兩個版本的原始碼（`master` 與確認正在使用的 `0.10.5` tag）核實，兩者程式碼一致。

### Goal 1 成功：用讀取 watchpoint＋暫存器覆寫跳過標題畫面，一路推進到存檔選擇畫面

既然寫記憶體行不通，改用讀取 watchpoint（`Z3`）盯住 `KEYINPUT`（`0x04000130`），在遊戲程式碼**執行讀取指令那一刻**（`gba->memory.io[]` 剛被寫入正確值、CPU 尚未把它讀進暫存器完成之前）用 `P` 封包直接覆寫「剛讀到這個值的目的暫存器」（本例是 `r1`），連續覆寫多個畫格（模拟「按住」），再放手讓後續幾個畫格自然讀到「放開」的值（製造完整的按下→放開邊緣，同時涵蓋「持續按住判斷」與「邊緣觸發判斷」兩種遊戲邏輯寫法）。

**重要操作細節（下次重跑必讀）**：
- 遊戲一開機（`pc=0`）就有 KEYINPUT 讀取——但那是開機／系統初始化階段的讀取（本輪在 `pc=0x0800077a`／`lr=0x0800103f` 這個位址捕捉到，開機後僅約 0.1–0.3 秒內就會命中），此時 `DISPCNT` 還在開機動畫的中間過渡狀態（本輪見過 `0x4012`，mode2，明顯是不同於標題畫面的另一個過渡畫面，很可能是 SEGA／片頭 logo 的縮放動畫），對這個讀取覆寫暫存器**完全沒有效果**——遊戲邏輯此時大概率還在跑固定長度、不讀取／不處理輸入的開場流程。**必須先讓模擬器自由跑到確認的穩定標題畫面（`DISPCNT == 0x1240`，第二輪已確認的值）再設 watchpoint**，本輪用「`c` 幾秒＋`interrupt` 檢查 `DISPCNT`＋不符合就再 `c`」的迴圈做到這件事，實測約 5 秒（機器全速執行，非依賴真實時鐘）就能穩定到達 `0x1240`。
- 命中的 KEYINPUT 讀取指令位址（`pc=0x0800077a`）在標題畫面穩定狀態、乃至於後續所有畫面，都是**同一個位址**——這是遊戲引擎一個共用的「每畫格讀一次輸入」工具函式，不是每個畫面各自寫一份輪詢邏輯，所以同一套 watchpoint／覆寫手法可以直接套用到後續畫面，不需要每個畫面重新定位輪詢點。
- 覆寫值：`KEYINPUT` active-low，10 個有效位元，「沒按」讀回 `0x3FF`；本輪用 `0x3FF & ~0x09`（同時按 Start 位元3與 A 位元0）模擬「按下 Start 鍵進入下一步」，後續用 `0x3FF & ~0x01`（單按 A）模擬「確認／選取」。每次覆寫維持 20–30 個連續畫格再放手，實測足夠讓遊戲的邊緣判斷或持續判斷都能感應到。

**確認跑到的畫面（依序，皆已渲染＋人工核對，非猜測）**：
1. **模式選擇畫面**（`research/mode-select-screen-obj-render.png`，OBJ tile 合成，用 OAM 實際座標／形狀／調色盤欄位而非單純方格排列）：標題「シャイニング・ソウル」縮小移到上方，下方新增兩行可選項目——「シングルプレイモード」（單人遊玩模式，橘色高亮＝目前選取項）與「マルチプレイモード」（多人遊玩模式，綠色＝未選取）。這批文字使用**與標題畫面「PUSH START」不同的全新片假名字形 tile**（VRAM OBJ tile 編號 44–67，原本只用到 0–47），證實 OBJ 字型系統確實是「共用同一批渲染機制、依畫面動態載入不同字符」的可重用字型，而不是每個畫面各自的專屬美術點陣圖——這正是第二輪報告裡標記為「證據偏弱、只看過一組字串」的缺口，本輪已補上第二組獨立字串。
2. **存檔選擇畫面**：`DISPCNT` 變為 `0x1d40`（BG0／BG2／BG3／OBJ 四層同時啟用，之前的標題／選單畫面只用 BG1＋OBJ），BG0（screenbase `0xe000`）目前為空／未使用內容，BG2（screenbase `0xf000`，`research/save-select-screen-bg2-char-stats-render.png`）顯示 4 組角色狀態預覽，各自有「Lv.」「エリア」（區域／地圖）「ATK」「DEF」「DEX」「STR」「VIT」「INT」等英文縮寫＋日文標籤混排的屬性欄位（模板尚未填入實際數值，符合「空白存檔」的預期），BG3（screenbase `0xf800`，`research/save-select-screen-bg3-file-slots-render.png`）顯示「FILE 1」「FILE 2」「FILE 3」「FILE 4」四個存檔格與「SELECT」「PAGE」等純 ASCII 字樣，格子本身是純色矩形 UI 元件（非文字）。四個 BG 共用同一個 charbase（`0x0`），只是 screenbase 不同——這代表整組 UI 文字／圖塊共用同一份 4bpp tile 字符資料，佐證這是統一的文字＋UI 渲染系統，不是分散、各自為政的美術資源。
3. 尚未繼續往下（例如進入「FILE 1」建立新角色的畫面）——本輪在拿到存檔選擇畫面的渲染確認後即停止，避免無限延伸偵察範圍；下一步的按鍵序列（例如對 FILE 1 送出 A）留給下一輪或後續工作。

**這對文字系統偵察的意義**：現在有三個獨立畫面（標題、模式選擇、存檔選擇）用同一套 OBJ／BG 字型 tile 機制渲染出不同組合的可辨識文字（片假名、漢字縮寫、純 ASCII），且 BG2／BG3 的 tilemap 資料本身（`0xf000`／`0xf800` screenbase 處的 16-bit tile-index 陣列）就是「字元代碼→畫面呈現」的直接映射——**下一輪要解 codepage，最快的路是直接讀取這些 tilemap 裡的 tile-index 序列，反查每個 tile 對應的字符圖形，而不是繼續從 ROM 靜態猜字串位置**，這與 ROADMAP 原本的建議方向一致，現在有了三個可重複、可即時採樣的具體畫面可用。

### Goal 2：找到字型／圖塊搬入 VRAM 的真實呼叫鏈，但「codepage 索引邏輯」仍未找到（誠實記錄一次錯誤路線）

**先記錄一次繞路**：一開始直接對已知的字型 tile 目的位址之一 `VRAM 0x06010000` 設寫入 watchpoint（`Z2`），命中後回溯發現來源是 ROM `0x0846fee4`（不是已確認的字型範圍 `0x62AA44`–`0x62B8E4`）——追查後這是**雲層背景動畫**的其中一格畫面，每約 10 個畫格重繪一次同一份 32 bytes（8-word）資料到同一個 tile 槽位，恰好與字型 OBJ tile 集合共用位址空間但屬於不同子系統。這代表第二輪報告裡「40/48 格...找到逐位元組相同的原始拷貝」時被排除的那 8 格假陽性裡，至少有 1 格（`0x6010000` 本身）其實正是被這個背景動畫覆寫的槽位，不是字型系統的一部分——這修正並非推翻第二輪的字型位置結論（那 40 格本身仍然成立），只是釐清了哪些 tile 編號屬於哪個子系統。改成直接對**已確認的字型來源** ROM `0x0862AA44` 設**讀取** watchpoint 後，才穩定命中真正的字型搬移路徑（約 3.5 秒內命中，遠比寫入 watchpoint 卡在背景動畫迴圈快得多）。

**已確認**（透過即時單步追蹤，非靜態猜測）：
- 字型 tile 資料透過**真正的 `swi`（BIOS CpuSet／CpuFastSet）指令**搬入 VRAM，不是簡單的 CPU 迴圈手動複製，也不是本輪之外任何形式的自訂壓縮——單步追蹤清楚看到 PC 落在 ARM 異常向量 `0x00000008`（SWI vector）。這與第二輪「137 個壓縮相關 swi（`0x10`–`0x18`）候選全部無法確認」的負面結果**不衝突**：此處用的是搬移／填充類 BIOS 服務，根本不在第二輪掃描的 `0x10`–`0x18`（壓縮專用）範圍內，兩者是互補而非矛盾的發現。**具體 swi 立即值已直接讀取 ROM 位元組＋capstone 反組譯確認、非推測**：ROM file offset `0x503bc`–`0x503bf` 是 `svc #0xc; bx lr`（`CpuFastSet`），`0x503c0`–`0x503c3` 是 `svc #0xb; bx lr`（`CpuSet`）——兩個都是「一條 svc 立刻接 `bx lr`」的極小包裝子程式（wrapper stub），不是 swi 指令本身所在的迴圈主體。
- 這兩個 swi wrapper 是被一段可反覆執行的**通用「傳輸佇列」迴圈**（ROM file offset 約 `0x11a0`–`0x11fe`）用 `bl` 呼叫的：迴圈走訪一個 12-bytes-per-entry 的陣列（每筆＝來源指標＋目的指標＋模式／長度欄位），依 entry 的 mode 欄位高位決定呼叫 `bl 0x80503bc`（file offset `0x11c4`，小型/固定大小傳輸）還是 `bl 0x80503c0`（file offset `0x11e6`，一般傳輸），執行完後歸零佇列長度。（先前一版文件把 `0x080011c6` 誤寫成「swi 呼叫本身發出的位址」——那其實是 `bl` 呼叫指令的位置，swi 真正所在位置是上一句確認的 `0x503bc`／`0x503c0`；已訂正。）這個迴圈同時服務**至少兩種資料**：本輪観察到的字型 tile 搬移，以及背景雲層動畫的逐格重繪（見上方繞路記錄）——換言之這是遊戲引擎共用的「VBlank 佇列化 VRAM／OAM／調色盤更新」機制，不是字型專屬的載入器。
- 反組譯（`file offset 0x1140`–`0x1220`，`/usr/bin/python3` + capstone，THUMB 模式，已用 `cpsr` 的 T bit=1 核對過模式判斷正確）看到這段迴圈本身結構清楚（`bhs`／`bge`／`blo` 分支、`bl` 呼叫、`ldr`/`str` 存取 12-byte entry），品質遠高於第二輪對壓縮 swi 候選的反組譯（那批因為錨點是猜的，反組譯出大量 GBA 不存在的協處理器指令；這次錨點是即時追蹤出來的真實執行位址，反組譯結果乾淨自洽，沒有出現任何不合理指令）。

**未確認／已測試但否定的假設**（誠實記錄，避免下次重工）：
- 原本猜測 ROM `0x08001154`（一段看起來像「把 (src,dst,mode) 三個參數存進佇列 entry」的小函式）就是字型專屬的 enqueue／推入呼叫點，在該位址設中斷點後連續攔截**150 次**呼叫，`r0`（來源指標）**沒有一次**落在已確認的字型 ROM 範圍（`0x0862AA44`–`0x0862B8E4`）內——全部是 OAM 影子緩衝區（`0x03001d40`→`0x07000000`）、調色盤影子緩衝區（`0x03002950`→`0x05000000`）之類每畫格固定執行的「影子緩衝區→硬體」搬移，與字型無關。改成直接在傳輸佇列迴圈頂端（`0x080011b4`）設中斷點、每次命中都窺視 `[r4]`（entry 的來源欄位）連續攔截 **400 次**，同樣沒有看到字型範圍的來源值。這代表：**字型 tile 的搬移確實有經過這個共用佇列迴圈**（已用讀取 watchpoint 直接證實過一次，錯不了），**但目前找到的「推入」函式候選（`0x08001154`）測試後被否定，不是字型使用的推入路徑**——可能是另一個獨立的推入函式，也可能字型搬移在開機極早期只發生一到兩次、不落在本輪攔截的畫格範圍內，尚未查明。**這是本輪明確標記為「已測試、未證實」的一條假設，不當成結論使用**。
- 因此，「哪一段程式碼決定要把哪個字型 tile（對應哪個字元代碼）排進佇列」——也就是 ROADMAP 步驟 3 要找的「字元代碼→字形 tile 索引」codepage 對照表——**仍未定位**。本輪找到的是它下游的通用搬運機制，不是它本身的決策邏輯。下一輪建議直接從上方「Goal 1 意義」提到的 BG2／BG3 tilemap tile-index 序列反查，可能比繼續往上追這條呼叫鏈更快。

### `gdbstub_client.py` 協定備忘（供下次直接照做，不必重新對照原始碼）

- `Z<type>,<addr-hex>,<kind-hex>` / `z<type>,...`：`type` 0/1＝中斷點，2＝寫入 watchpoint，3＝讀取 watchpoint，4＝讀寫 watchpoint；成功回 `OK`，不支援的 type 回空字串（不是錯誤碼，呼叫端要對兩種都判斷）。
- `P<regno-hex>=<value>`：`value` 是暫存器 4 bytes 的**小端序**（ARM target 位元組序）hex，跟 `g` 封包讀出來的格式一致，**不是**直接把數值當十六進位數字編碼——寫 `write_register()` 時務必用 `value.to_bytes(4,'little').hex()`，不要直接 `f'{value:08x}'`。
- `c`（continue）不會立即回應；等到中斷點／watchpoint 命中才會收到非同步的 `T05...;` 封包（watchpoint 命中會附 `watch:`／`rwatch:`／`awatch:` 加位址）。這個封包本身仍是標準 `$...#xx` framing，可以直接用既有的 `_read_packet()` 消化，只是要给一個遠比一般指令回覆更長的逾時（`cont_and_wait()` 已內建）。
- **中斷點／watchpoint 命中後，如果不先 `s`（single step）一次就直接再 `c`，會立刻在同一個 PC 上重新命中**（尤其是寫入 watchpoint 卡在一個緊湊複製迴圈裡時，會看起來像「暫存器完全不變」，很容易誤判成單步沒有生效——其實是同一個未跨過的指令被反覆重新命中）。命中後一律先 `s` 一次再繼續，除非明確要利用這個特性連續攔截同一個輪詢點（例如本輪對 KEYINPUT 讀取的做法，那裡的重複命中是預期行為，因為每次都是新的一個畫格）。

## 第四輪偵察（存檔選擇畫面 BG 字型表：找到字型表本體＋部分 codepage）

工具環境同第三輪。本輪新增 `games/shining-soul-1/tools/navigate_and_dump.py`（把第三輪
「跳過標題畫面／推進到存檔選擇畫面」的按鍵注入流程寫成可重跑腳本，第三輪只有文字描述、
沒有存成腳本）與 `games/shining-soul-1/tools/extract_bg_fonttable.py`（擷取／驗證／渲染
本輪找到的 ROM 字型表）。詳細方法、完整 codepage 表、confirmed／未確認分級，見專門的
`research/bg-fonttable-codepage-partial.md`（分析結論，非原文，可提交）。

**本輪重跑 `navigate_and_dump.py` 時的一個教訓**：第一次執行時在按鍵注入迴圈裡多加了一次
`s`（single-step），且「標題畫面已穩定」的等待時間太短（DISPCNT 剛變成 `0x1240` 就立刻視為
穩定），結果整個流程原地打轉，兩次「按鍵」都完全沒有效果（`DISPCNT` 全程停在 `0x1240`，
OAM 渲染出來還是標題畫面本身）。同時拿掉多餘的 single-step、並在偵測到 `0x1240` 後再多
free-run 約 4 秒才真正設 watchpoint（**兩個改動一起做**，沒有分開驗證是哪一個真正解決了問題，
下次如果同樣的手法又失敗，應該先分開測試這兩個變因，而不是預設兩個都必要），第二次就穩定成功
推進到存檔選擇畫面（`DISPCNT=0x1d40`，與第三輪記錄一致）。可以確定的教訓：**「DISPCNT 讀到
目標值」不等於「畫面已經穩定到能接受輸入」**，尤其是可能還在淡入／淡出過渡幀的時候；下次一樣
的手法要記得抓多一點穩定緩衝時間。整個過程都設了明確逾時
（`cont_and_wait` 帶 timeout、bash 呼叫本身也不依賴無窮等待），沒有發生掛住不回應的情況。

**已確認、重大結構性發現**：存檔選擇畫面的 BG2（`screenbase 0xf000`）／BG3（`screenbase
0xf800`）都用 `charbase 0x0`；ROM file offset **`0x1398e8`** 是一張 **1024 格**（0–1023，
剛好是 4bpp tilemap tile-number 欄位的完整定址範圍）、每格 32 bytes 的字型表，總長度
`0x8000`，結束於 `0x1418e8`。**已用窮舉逐格比對確認**：存檔選擇畫面實際載入的 VRAM
charbase `0x0` 內容與這整段 ROM 範圍逐位元組完全相同，覆蓋全部 1024 格，第一個不相符位置
剛好落在 tile-index 1024（定址範圍邊界本身，不是提早分歧）——這代表 BG tilemap 的
tile-number 欄位是直接定址進這張表，**tile-index 本身在這條渲染路徑上就是字符代碼**，
不存在另一層「字符代碼→tile-index」的間接對照要另外找。這張表與第二輪確認的 OBJ 字型
（ROM `0x62AA44`–`0x62B8E4`，標題／模式選擇畫面用）位置完全不同，是兩套獨立系統——目前
仍不知道對話文字（如果之後找到）用的是這兩套裡的哪一套，還是第三套。

**已確認的部分 codepage**（約 32 個相異字符，片假名＋Latin 字母＋數字，來自 FILE／SELECT／
PAGE／ATK／DEF／DEX／STR／VIT／INT／Lv. 等已知文字）：完整表格、confirmed／中信心／
低信心分級、以及每一條的驗證方式，記在 `research/bg-fonttable-codepage-partial.md`，
不在此重複列出以免兩處不同步。摘要重點：
- 這是一套**窄體壓縮字型**——多數 Latin 字母是兩個半形字元塞進同一格 8×8 tile（例如一格畫
  "FI"），只有片假名和少數數字／收尾字母是嚴格一格一字。嚴格「一個 tile-index＝一個字符」
  的假設**不成立**，下一輪如果要繼續擴充這張表，需要先弄清楚哪些格是 packed、哪些不是。
- 找到目前為止唯一一個「同一 tile-index 被兩個不同標籤共用」的直接證據（tile 112 的「DE」
  同時被 DEF 與 DEX 標籤引用，逐位元組核對確認），支持這確實是可重用字型系統而非各自獨立
  美術；但也發現同樣內容在表裡有第二份獨立拷貝（tile 118，內容與 112 相同但是不同 index），
  以及至少 4 個視覺相似但逐位元組互不相同的「▷」三角形圖示——這套系統顯然沒有做嚴格去重複，
  細節仍有不少沒解釋清楚的地方。
- 「同一個字符在不同情境下可能是不同 tile-index、不同字形」已有具體反例：FILE 方框樣式的
  數字「1」（tile 87）與 PAGE 頁碼樣式的數字「1」（tile 81）逐位元組核對確認**不是**同一份
  資料——同一遊戲內至少有兩種視覺上不同的「1」。
- **項目 1（是否為跨畫面共通的系統級 codepage）本輪未完成**：目前只有存檔選擇畫面成功
  讀到 BG2／BG3 內容；重新造訪的標題／模式選擇畫面只啟用 BG1＋OBJ，不使用 BG2／BG3，
  沒有機會做跨畫面對照。字型表圖片裡有一段低信心判讀懷疑是「キャラクタ／カラーセンタク」
  （角色／顏色選擇），如果屬實會是角色建立畫面的 UI 文字——這與 ROADMAP 原本建議的下一步
  （選取 FILE 1 建立新角色）直接對應，是下一輪驗證這一點的好機會。

## 中文譯名核對

`game.yml` 的 `zh-Hans`／`zh-TW` 標題採用「光明之魂」，依專案「專有名詞音譯政策」核對後決定：巴哈姆特 ACG 資料庫（`acg.gamer.com.tw`，條目 `s=3915`）明確使用「光明之魂」；另有多個獨立中文遊戲站台（`indienova.com`、`99danji.com`、`sptuner.blogspot.com` 等）不約而同使用同一譯名，未發現任何分歧版本。維基百科中文版似乎沒有這款遊戲的獨立條目（查詢「光明與黑暗系列」條目及站內搜尋皆未命中），因此本次未能取得政策要求的「Wikipedia＋巴哈姆特」雙來源中的 Wikipedia 那一份；但多個獨立巴哈姆特以外站台一致無異議，已達到政策「不只看單一來源」的精神，故採用「光明之魂」而非留白或自創音譯。目錄檔名本身也是「光明之魂1」，與此結果一致（但目錄檔名本身不算獨立來源，只是佐證）。

`titles.ja` 的「シャイニング・ソウル」是常見寫法，但**未經 ROM 驗證**——卡匣標頭的標題欄位是純 ASCII `SHINING SOUL`，沒有片假名資訊可比對；片假名寫法只是外部慣例，非本輪偵察的直接證據。

## ROM 識別

| 項目 | 值 |
| --- | --- |
| 目錄檔名 | `0379 - 光明之魂1 Shining Soul(JP)(Sega)(64Mb).zip`（原始檔名以 GBK 編碼儲存，非 UTF-8，`unzip` 直接解壓會因編碼不符報 `Illegal byte sequence`，須改用能指定來源編碼的工具，如 Python `zipfile` + 手動 `cp437→gbk` 轉碼） |
| 卡匣標頭標題（offset `0xA0`,12 bytes） | `SHINING SOUL` |
| game code（offset `0xAC`,4 bytes） | `AHUJ` |
| maker code（offset `0xB0`,2 bytes） | `8P` |
| 標頭固定值（offset `0xB2`） | `0x96`（正確） |
| 標頭補數校驗（offset `0xBD`） | `0x2e`，與 `-(sum(0xA0..0xBC)) - 0x19` 計算值相符 |
| 檔案大小 | 8,388,608 bytes（0x800000） |
| CRC32 | `521450d1` |
| MD5 | `0cb9989beb289f843cdb69bb0bd8c8be` |
| SHA-1 | `5fe69468dc1ecd9fb40f0ab3ca361963006dbb02` |
| SHA-256 | `7adebc47af58a7cb12c6e862482e3fd1b2cb82aab2dc3a556ac93f9e78df6b28` |
| ROM 實際使用範圍 | `0x000000`–約 `0x660000`；`0x660000`–`0x800000` 全為 `0xFF` 填充 |

以上雜湊只是本機記錄，**未與任何 No-Intro／GoodGBA 等外部資料庫核對**——這點與黃金太陽兩個工作區不同，那邊的雜湊已經是多次構建反覆驗證過的基準；本遊戲目前只有這一次讀取，僅代表「這個檔案的雜湊是這些值」，不代表「這些值已知是正確的無損 dump」。

## 已完成的唯讀掃描（工具與方法）

以下腳本在 `games/shining-soul-1/tools/` 底下，第一輪四支對 ROM 檔案全部唯讀（只 `open(..., 'rb')`，不寫回 ROM），可重跑取得完全一致的結果：

```sh
python3 games/shining-soul-1/tools/scan_compression_signatures.py \
  games/shining-soul-1/roms/base/Shining_Soul_JP_AHUJ8P.gba --align 2

python3 games/shining-soul-1/tools/scan_swi_calls.py \
  games/shining-soul-1/roms/base/Shining_Soul_JP_AHUJ8P.gba --align2

python3 games/shining-soul-1/tools/scan_pointer_tables.py \
  games/shining-soul-1/roms/base/Shining_Soul_JP_AHUJ8P.gba --min-run 20

python3 games/shining-soul-1/tools/scan_sjis_runs.py \
  games/shining-soul-1/roms/base/Shining_Soul_JP_AHUJ8P.gba --min-chars 10
```

各腳本的方法論限制都寫在腳本自己的 docstring 裡（例如「合法 Shift-JIS 結構不代表真的是文字」「位元組層級的 magic byte 掃描沒有做程式碼交叉比對」），避免未來誤把候選當成已確認結果。掃描的精簡輸出留存於 `research/compression-signature-scan.txt`、`research/swi-call-scan.txt`（本機、不進 Git）。

第二輪新增三支工具（用法與方法論限制見上方「第二輪偵察」一節與各自 docstring）：

```sh
# 反組譯覆核 swi 候選（需要 /usr/bin/python3，capstone 只裝在這個直譯器上）
/usr/bin/python3 games/shining-soul-1/tools/disasm_swi_calls.py \
  games/shining-soul-1/roms/base/Shining_Soul_JP_AHUJ8P.gba

# mGBA GDB stub 用戶端（函式庫用法，見檔案內 __main__ 範例；需先 `mgba -g <rom>` 背景啟動）
/usr/bin/python3 games/shining-soul-1/tools/gdbstub_client.py

# VRAM tile/tilemap 渲染成 PPM（供人工視覺核對字形/圖像，用法見 docstring）
/usr/bin/python3 games/shining-soul-1/tools/render_vram_tiles.py <vram.bin> <pal.bin> \
  --charbase 0x0 --screenbase 0xe800 --bpp 4 --out out.ppm
```

第四輪新增兩支工具（用法與方法論見上方「第四輪偵察」一節、`research/bg-fonttable-codepage-partial.md`、各自 docstring）：

```sh
# 自動跳過標題畫面、推進到存檔選擇畫面，dump VRAM/palette/OAM（唯一會寫模擬器狀態的工具，不寫 ROM 檔案）
/usr/bin/python3 games/shining-soul-1/tools/navigate_and_dump.py --out-dir /tmp/ss1_dump
# 需先背景啟動：/opt/homebrew/bin/mgba -g games/shining-soul-1/roms/base/Shining_Soul_JP_AHUJ8P.gba &

# 擷取／驗證／渲染 ROM 裡確認到的 1024 格 BG 字型表（ROM 0x1398e8 起）
/usr/bin/python3 games/shining-soul-1/tools/extract_bg_fonttable.py \
  games/shining-soul-1/roms/base/Shining_Soul_JP_AHUJ8P.gba \
  --out-bin /tmp/fonttable.bin --out-png /tmp/fonttable.png \
  --palette /tmp/ss1_dump/03_save_select.pal.bin \
  --verify-against /tmp/ss1_dump/03_save_select.vram.bin
```

## 下一步（供下一輪偵察或動手解碼參考）

**已確認、不必重做**：BIOS 壓縮呼叫候選已用反組譯覆核過，全部無法確認為真指令；title／模式選擇／存檔選擇三個畫面的渲染，GBA 4bpp/32-bytes-per-tile 格式假設，OBJ 字形資料在 ROM `0x62AA44`–`0x62B8E4` 附近的位置，都已用視覺渲染＋逐位元組比對確認（見上方「第二輪偵察」「第三輪偵察」）。直接寫 `KEYINPUT` 記憶體無效的根因已對照 mGBA 0.10.5 原始碼確認（`GBAIORead` 每次讀取都會用 `keysActive`／`keyCallback` 覆寫該位址，架構性地不可能用純記憶體寫入模擬按鍵）；改用讀取 watchpoint＋暫存器覆寫已能穩定跳過標題畫面並推進到存檔選擇畫面（`navigate_and_dump.py` 已把整套流程寫成可重跑腳本）。渲染時務必先分清 VRAM offset 落在 charblock（像素）還是 screenblock（tilemap）範圍。**第四輪新增**：存檔選擇畫面 BG 文字用的 1024 格字型表本體已定位在 ROM `0x1398e8`–`0x1418e8`（窮舉逐格比對確認，見「第四輪偵察」），約 32 個相異字符的部分 codepage 已建立（見 `research/bg-fonttable-codepage-partial.md`）；這與 OBJ 字型（`0x62AA44`–`0x62B8E4`）是兩套獨立系統。

1. **最高優先**：推進到角色建立畫面（在存檔選擇畫面對 FILE 1 送出 `A`），用 `navigate_and_dump.py` 已驗證的按鍵注入技巧（讀取 watchpoint 盯 `KEYINPUT` `0x04000130`＋`P` 封包覆寫目的暫存器）應該可以直接推進。這同時服務兩個目的：(a) 這是 ROADMAP 一直建議的「更直接考驗文字輸入系統的畫面」；(b) 第四輪在 BG 字型表裡目測到疑似「キャラクタ／カラーセンタク」（角色／顏色選擇）字樣（低信心、未核對），如果角色建立畫面真的用到這批 tile-index，會是「同一張表跨畫面共用」的第一個直接證據——這正是第四輪 README 任務指定但未完成的「項目 1」。
2. 擴充 `research/bg-fonttable-codepage-partial.md` 裡「低信心／僅結構性判讀」那些條目——tile 0–9、16–25 兩組額外數字樣式、tile 91–94 疑似 5–8、tile 176–191 疑似另一份 FILE+數字拷貝——目前都只從字型表圖片目測，沒有在任何實際畫面上看過被引用，需要找到會用到它們的畫面才能核實。
3. 找到字型搬移的通用「傳輸佇列」機制本身之後，回溯是哪段程式碼把 (來源=字型 ROM 位址, 目的=VRAM tile 槽, mode) 三元組寫進佇列 entry——本輪測試過的候選推入函式（ROM `0x08001154`）已用 150＋400 次即時攔截**否定**，不是字型使用的推入路徑，需要換一個候選或换一種找法（見上方「第三輪偵察」Goal 2 一節「未確認／已測試但否定的假設」）。這條路線優先度低於上面兩點，因為 tile-index 已確認直接對應 ROM 字型表位址，不再迫切需要靠這條呼叫鏈反推 codepage。
4. 仍未解決：對話文字（量遠大於 UI 提示字樣）究竟走 BG／OBJ 這兩套已知字型表的哪一套（或完全是第三套系統）；本輪確認的兩張字型表都只涵蓋片假名＋Latin 字母＋數字，沒有 hiragana、沒有漢字，不能假設就是對話文字系統。文字究竟是 BIOS 壓縮、自訂壓縮、還是完全不壓縮直接存放也仍未解——第二、三輪確認的是「字型 tile 搬移」不經壓縮，但那只涵蓋固定 UI 圖塊。

## skill 使用備註（`gba-localization`）

記錄給下一個使用這個 skill 的人／agent：

- 「Establish scope」步驟基本可直接照做，唯一落差是它假設 `**/research/` 已被 `.gitignore` 完整涵蓋（"already covered by .gitignore's `**/research/` patterns"）——**實測並非如此**。目前 `.gitignore` 只排除 `research/` 底下少數特定檔名樣式（`*-decoded.jsonl`、`*-text-ids.tsv`、`*.pgm`/`*.ppm`/`*.png`、`vendor/`、`ocr-samples/`），一般筆記檔（例如 `research/notes.md`、`research/header-dump.txt`）**不會**被排除，`git check-ignore -v` 可直接驗證。這與黃金太陽既有的 `games/golden-sun-the-lost-age/research/baseline-20260814.md` 是刻意被提交的分析文件（非原文）互相印證——`research/` 底下本來就分「可提交的分析結論」跟「不可提交的原文／衍生資料」兩類，只是新遊戲第一次接觸時很容易誤以為整個目錄都自動安全。建議在 skill 文字裡把這句改成「verify per-file, do not assume the whole directory is covered」，而不是暗示目錄本身受保護。本次偵察因此把一份較大的原始掃描輸出（`research/sjis-runs-raw.txt`，主要是誤判的假陽性內容，非遊戲原文）在寫入後又刪除，改成只留精簡摘要，避免留下一個未受 `.gitignore` 保護的大檔案。
- 「Recover source text locally」一段的核心提醒（「每款新遊戲都有自己的文字系統，不要假設它長得像黃金太陽的 Huffman 格式」）完全命中——這次 Shift-JIS／指標表兩個最直覺的假設都被證偽，如果不是 skill 明確提醒要「看實際存在什麼」而不是照搬黃金太陽的做法，很可能會浪費更多時間在錯誤方向上（例如直接套用黃金太陽的 Huffman 指標表格式去找）。
- 這段流程沒有覆蓋到的部分：對於「連文字大致存放區域都還沒鎖定」的全新遊戲，skill 沒有給出具體的偵察方法論或工具建議（例如熵分析找程式碼／圖形／填充邊界、BIOS `swi` 呼叫點掃描、Shift-JIS 結構掃描要如何過濾假陽性）——這些是本次臨時寫的腳本，可能值得日後抽成 skill 裡的共用建議或 `core/` 下的可重用工具，而不是每款新遊戲都重新發明。目前 `games/shining-soul-1/tools/` 底下四支腳本都是遊戲無關的通用 ROM 掃描邏輯，唯一遊戲相關的地方只有呼叫參數（ROM 路徑）——這類工具或許該挪到 `core/` 供未來新遊戲直接引用，而不是留在 `games/shining-soul-1/tools/` 裡讓下一款遊戲重寫一遍。本次先留在遊戲目錄下，因為尚未有第二個使用案例佐證真的可重用。
- Zip 檔名編碼（GBK 而非 UTF-8）導致 `unzip` 直接失敗，skill 沒有提到這個常見障礙；已在上方「ROM 識別」記下繞過方法（Python `zipfile` 手動轉碼），供下次快速解決同類問題。
- 第二輪心得：skill 建議「渲染字型＋OCR」或「模擬器中斷點觀察 VRAM」作為 Shift-JIS／指標表都找不到時的備案，這次證實**後者比純靜態反組譯有效得多**——花在「用 capstone 覆核 swi 候選」上的時間只換到一個強化版負面結果（137 個候選全部無法確認），而改用 mGBA GDB stub 直接觀察執行期 VRAM，一次就拿到「畫面渲染吻合＋字形格式確認＋部分字形資料 ROM 位置」三項正面結果。教訓：**對於「連文字大致存放區域都還沒鎖定」的新遊戲，如果有能力起模擬器，應該優先於純靜態反組譯**，因為靜態反組譯在沒有從 entry point 做完整控制流重建的情況下，對 THUMB 這種密集編碼指令集的「這是真指令」判斷力很弱（見上方「反組譯結果」一節）。
- 第三輪心得：mGBA GDB stub 支援的功能比「純輪詢記憶體」豐富得多（watchpoint＋暫存器寫入＋非同步 stop-reply），但這些能力**沒有寫在任何 GDB remote protocol 通用文件裡能直接照搬**——mGBA 的 stub 是部分實作，正確用法（封包格式、位元組序、命中後要不要先 `s` 再 `c`）只能對照它自己的原始碼（`src/debugger/gdb-stub.c`）核對，用「照 GDB 標準協定文件猜」會在暫存器位元組序（`P` 封包）這種細節上出錯而不自知。另外一個具體教訓：遇到「寫記憶體看起來完全無效」的情況，不要停在「時機不對／格式不對」的猜測，直接去讀模擬器原始碼確認**這個位址的讀取路徑是否本來就會覆寫記憶體內容**（本輪的 `KEYINPUT` 正是這種情況）——這比反覆調整寫入時機／數值快得多，也才是真正的根因而非表面現象的修補。
- 第四輪心得（game-agnostic，值得留在這個 skill 而非只留在本遊戲文件）：**當畫面上已知會顯示什麼文字時（UI 標籤、選單提示等固定字串），直接讀取 tilemap 的 tile-index 陣列＋逐格用正確 palette bank 渲染核對，比 OCR 或統計投票快得多、也精確得多**——本輪完全跳過 OCR，單靠「已知答案」反查，一次就拿到約 32 個字符的 confirmed／分級碼表，且順藤摸瓜找到整張 1024 格字型表的 ROM 位置。這是 skill 文件裡「Two separate problems」一節目前只列了「raster byte-matching」與「render+OCR」兩種 codepage 取得法，這次證實還有第三種、成本更低的路徑：**當遊戲畫面本身包含已知明文時，直接用它當 ground truth，跳過 OCR**——但這只在「碰巧有已知明文畫面」時才適用，不是所有情境都能套用，是這兩種既有方法之外的機會主義捷徑，不是取代品。另外一個教訓：「DISPCNT 讀到目標值」不等於「畫面已經穩定到能接受輸入」，可能還在淡入淡出過渡幀——用「continue 一段時間＋讀 DISPCNT＋不符合就再 continue」的迴圈判斷穩定時，建議在第一次讀到目標值後再額外多等一段緩衝時間，而不是立刻信任第一次命中。

## 合規邊界

公開倉庫只保存工具、偏移、雜湊、研究結論及有權分享的翻譯資料。使用者必須自行提供合法 ROM；不發布 ROM、來源不明字型，或可還原大段原作腳本的資料。本輪偵察未產生任何翻譯資料，`translations/` 目錄尚未建立。

詳見[路線圖](ROADMAP.md)。
