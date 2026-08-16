# 《世界傳說：召喚者的血統》工作路線

## 里程碑 0：乾淨基準與唯讀偵察

- [x] 建立獨立 game slug、`game.yml`、README 與研究帳。
- [x] 確認日版候選 A9PJ、標頭欄位、大小、CRC32、MD5、SHA-1、SHA-256。
- [x] 記錄標頭 checksum mismatch，不把 dump 當成完全 pristine。
- [x] 確認 literal Shift-JIS sentinel 全部為零命中。
- [x] 建立不輸出原文的 ROM 結構掃描器、指標／壓縮資源探針與 patch 工程探針。
- [x] 確認兩張大型指標表可逐項解碼為 GBA LZ77 資源；暫不誤認為劇本文字。
- [x] 保存 v0.20 patch 的工程雜湊與局部差異統計；patch 二進位檔不進 Git。

## 里程碑 1：文字系統與可逆試補丁

- [x] 在獨立 `23901` listener 完成一次有界 read-watchpoint capture；receipt 與負結果
  已記錄，沒有把 stub `OK` 當成文字命中。
- [x] 使用共用 `core/gba` 完成 1 秒／5 秒 startup runtime baseline，並以共用 BG／OAM
  renderer 重建實際 graphics layer；研究結論不把 graphics 當成文字證據。
- [ ] 從原 ROM 的候選 pointer／record 結構分離劇情、地圖／事件、角色、戰鬥與
  圖像／字型資料。
- [ ] 以 mGBA GDB watchpoint／VRAM 證據確認至少一條實際文字渲染路徑；記錄讀取
  位址、碼元與字形資料位置。
- [x] 定義日文 source table 的本機欄位、proof gate 與 ledger restore／strip 接線；
  規格見 `research/source-table-spec-20260816.md`。
- [ ] 解出 16-bit codepage、字形身份與控制碼；把「能定位 glyph」與「知道 glyph
  是哪個字」分開記錄。
- [ ] 寫出可重跑 decoder，輸出本機 `research/*-decoded.jsonl`，不提交原文。
- [ ] 建立日文來源的 checksum／decoder version，讓 ledger restore 能偵測漂移。
- [ ] 建立只含少量 UI／短句的回插試驗，重新抽取逐 byte 驗證未修改區。

## 里程碑 1.5：第一個互動文字圖層切片

- [x] 以 A9PJ 已證實的 KEYINPUT read path 注入 `START, START, A`，抵達第一個
  name-entry／kana 互動畫面；不重做 startup logo baseline。
- [x] 使用共用 `core/gba` capture、BG tilemap 與 OBJ renderer，確認 BG0／BG1／BG3
  的實際圖層與 `DISPCNT`／`BGxCNT` 對應。
- [x] 把 glyph addressing（BG0 tile `0x125`、VRAM `0x060024A0`）與 glyph identity、
  codepage、控制碼分欄記錄；ROM exact match 僅保留為 byte／圖形候選。
- [x] 對 transition 與初始 boot 各做一次有界 1-byte VRAM write watchpoint；兩次均
  留下 `tile_hit_count=0` 的可重現陰性 receipt，沒有把人工 interrupt 當成 hit。
- [x] 取得實際 source buffer 與控制流上的文字 consumer／caller；M1.6 已確認一組
  code unit→font-record 關係，但 DMA 邊界、glyph identity 與控制碼仍未確認，source
  table／work ledger 維持空白。

## 里程碑 1.6：name-entry code-unit／font-record 有界切片

- [x] 以 BG1 `charbase=0x4000`、`screenbase=0x0800` 建立八個五十音鍵盤位置的
  tile ID／flip／palette／hash metadata；`[1,2,3,4,5,27,28,29]` 的固定 32-byte
  runtime stride 已由實際 tilemap 與 rendered grid 交叉確認。
- [x] 對八個 runtime tile 做 clean-ROM exact match；本次只有 1/8 個未對齊 accidental
  match、0/8 個 32-byte aligned match，因此 confirmed glyph identity 維持 `0`。
- [x] 以 adaptive `START` gate 後執行 `A, RIGHT, A`；三個取樣畫面均維持已確認的
  BG1 keyboard signature，EWRAM diff 收斂為第一格 `0x0001→0x005E`、第二格
  `0x0001→0x0066`，IWRAM 沒有 append candidate。
- [x] 對 `0x02004014` 重跑 one-shot writer／reader watchpoint：取得 writer
  `PC=0x08052BBC/LR=0x0806B66F` 與 reader `PC=0x080063B8/LR=0x080063C7`，
  並保留 code unit 與寄存器 receipt。
- [x] 由 reader caller `0x080049A0` 的 `code_unit * 0x18` arithmetic 反推出 ROM
  font-record base `0x08089E00`；這是 code-unit→font-record consumer 證據，不冒充
  runtime tile identity 或控制碼。
- [x] 擴充遊戲專用 metadata／diff／filter／address-math probe 與 5 個單元測試；raw
  記憶體、VRAM、圖片與 ROM 均留在 private／ignored 路徑。
- [ ] 取得 font-record 到實際 BG1 charblock tile 的直接 DMA／copy 或寫入證據，並以
  table arithmetic、runtime tile match 與鍵盤位置三者共同確認 glyph identity；gate
  通過前不建立 source table、work ledger 或翻譯。

## 里程碑 1.7：font-record → VRAM consumer 有界切片

- [x] 重用既有 BG1 keyboard gate 與 `A, RIGHT, A`，不重做 startup logo baseline；
  `DISPCNT=0x1B40`、`BG1CNT=0x0106`、BG1 `charbase=0x4000/screenbase=0x0800` 與
  八格 tile metadata/hash 前後一致。
- [x] 對 `0x005E`／`0x0066` 各取得一次實際 24-byte font-record read：
  `0x0808A6D0`／`0x0808A790`，並保留 record hash、stop PC/LR 與 alternate `ldrh`
  site；這不是只靠靜態 table arithmetic。
- [x] 以 `0x08004C82 str`、`0x08004D1A stm` breakpoint 反向取得 `r12-0x18` record
  pointer、context formula、CPU writer／LR、有效 VRAM destination 與 post-store tile
  hash；兩個 code unit 都落在 `0x060020xx/0x060023xx` 的非 BG1 VRAM slice。
- [x] 對 BG1 tile 1／2 各設 32-byte write watchpoint；命中 `0`，前後
  `0x06004020`／`0x06004040` hash 相同，留下可重跑的精確陰性。
- [x] 對 DMA3 control 做 bounded 前／後寄存器 receipt；觀察到的 setup 不含兩個
  font-record pointer，也沒有 BG1 destination；CPU／DMA／BIOS 分開記錄，未把它誤標
  成文字 DMA。
- [x] 擴充 `m17_font_tile_probe.py` 與 5 個純算術測試；重用 `core/gba` capture 與
  `render_vram.py`，raw／圖片／ROM 均留 private／ignored。
- [ ] 定位 BG1 keyboard 資產初始化自己的 source／DMA／copy caller，證明它與
  `0x005E`／`0x0066` path 的共同關係；目前 confirmed identity `0`、provisional `2`，
  其他 code units unknown，控制碼與 source table gate 維持關閉。

## 里程碑 2：可審核 zh-TW 翻譯帳本

- [ ] 先完成 Wikipedia zh-tw、Bahamut 與其他獨立社群來源的專有名詞核對；有分歧
  時保留工作名並記錄分歧，不自行定案。
- [ ] 建立人名、地名、角色、職業、技能、道具、戰鬥與地圖術語表。
- [ ] 以 `restore_translations.rb` 產生本機工作記錄，逐條補上 `zh-TW` 譯文、
  `context`、寬度／行數預算與控制碼說明。
- [ ] 以 `strip_translations.rb` 產生不含 `source` 的可提交 ledger；跑 schema、
  source hash round-trip 與 repository safety。

## 里程碑 3：完整回插與 QA

- [ ] 從乾淨 A9PJ ROM 產生可逆 patch，驗證 patched ROM 可重新抽取且 source hash
  不漂移。
- [ ] 完成地圖／事件／角色／戰鬥資料的文字覆蓋率盤點。
- [ ] 用 mGBA 完成標題、序章、地圖事件、戰鬥、存檔與結局等核心場景回歸；未測畫面
  明確列出，不假設成功。
- [ ] 只發布 patch／ledger／工具與研究結論，不發布 ROM、完整原文或未授權字型。
