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
  `0x005E`／`0x0066` path 的共同關係；keyboard table identity 已分別確認為
  `0x005E=あ`、`0x0066=う`，但 renderer transfer 仍 provisional，其他 code units
  unknown，控制碼與 source table gate 維持關閉。

## 里程碑 1.8：BG1 keyboard asset provenance 有界切片

- [x] 從 initial GDB stop 對 `BG1CNT=0x0400000A`、`0x06004020`／`0x06004040` 與
  DMA0–3 control 設置 bounded write watch；工具重用 `core/gba` client/capture，
  raw／圖片仍留 private／ignored。
- [x] 取得一次 BG1CNT writer receipt：`PC=0x080141FA/LR=0x080141F3`、value
  `0x0105`，反解為 charbase `0x4000`／screenbase `0x0800`。
- [x] 取得一次 reset-stage `0x06004020` write：writer PC `0x00000008`、分類為
  BIOS copy candidate，tile hash `02d449…`；它不等於 M1.6 keyboard tile-1 hash
  `b5ae444…`，所以沒有提升 glyph identity。
- [x] 留下 DMA control PC/LR 與 bounded protocol receipt；因暫存 mGBA 把
  `T05watch`／`S05`／`S02`／上一筆 data payload 延遲到下個 command，source／
  destination 欄位不採信，沒有把 `target_overlap=false` 冒充 DMA 排除。
- [x] keyboard gate 的失敗可重現：參考 receipt 兩次 START 後 BG1 八格全為
  `0x0000`，position match `0/8`；因此 keyboard transition 的 source→copy／DMA
  chain 尚未確認，M1.8 confirmed identity `0`。
- [x] 明確比較 M1.7 `0x080063C7`／`0x005E`／`0x0066` path：目前未見 shared LR、
  record pointer 或 caller；記為未連接的 renderer candidates，不合併 codepage。
- [ ] 在穩定 keyboard gate 後，以單通道／單次 DMA watch 或 `0x06004000` bounded
  slice 重新取得可信 source/destination，完成 source bytes/hash／copy transform 與
  BG1 tilemap 位置三方交叉；source table、控制碼、ledger 與翻譯維持關閉。

## 里程碑 1.9：strict gate／single-transfer provenance boundary

- [x] 以 fresh mGBA／獨立 `39123` listener／單一 GDB connection，將 ACK、delay、
  timeout/retry 與 response shape 檢查固定化；不沿用 M1.8 queued packet 欄位。
- [x] 以既有 `START, START, A` 上限導航，三個 clean process 重現
  `DISPCNT=0x1B40`、`BG1CNT=0x0106`、八格 `8/8` 與 tile-1/tile-2 hash gate。
- [x] 先做單一 `0x06004020` 32-byte write watch；keyboard gate 成立但 hit `0`，
  留下「不是 CPU／BIOS 可見 tile write」的精確 negative，不把它解讀成無 consumer。
- [x] 再做單一 DMA3 `CNT_H` setup/control watch；保留 observed `0x040000DC`、PC/LR、
  `CNT_H=0x8400` 與 source/destination/count metadata，但非 GBA source／destination
  與零 source match 使這筆維持 unknown，不宣稱 transfer receipt。
- [x] 更新 `m19_gate_transfer_probe.py`、strict response／DMA window tests 與研究
  receipt；ROM、raw、圖片、work/source 均未進 Git。
- [ ] 取得可信 DMA／CPU source bytes→VRAM byte-identical 或明確 transform receipt；
  這是後續獨立 runtime 缺口，不阻塞先從已確認 font-record consumer 開始建立私有
  metadata extractor。

## 里程碑 2A：文字 record／codepage／控制碼研究（持續清單）

- [x] 從 `0x02004014` code-unit consumer 與 `0x08089E00 + unit*0x18` arithmetic
  建立只輸出 metadata 的日版 record extractor；固定 `0x18` record geometry、完整
  16-bit table bounds、record hash 與 parser provenance，不輸出原文。
- [ ] 以 runtime pointer／caller／畫面語境把候選分離為劇情、地圖／事件、角色、戰鬥、
  UI／字型；pointer geometry 或候選壓縮表不得單獨標成文字。
- [x] 把 glyph addressing、glyph identity、codepage、terminator／control candidate
  分欄；目前是 `16-bit width confirmed`、兩個 runtime-backed keyboard identity
  confirmed（`0x005E=あ`、`0x0066=う`），另三個 row-0 table mapping confirmed，
  renderer transfer gate 仍 provisional；`0x0000` terminator parser branch 與
  `0xFF70` line-advance behavior candidate。
- [ ] 以 runtime reader／consumer 的 code-unit 序列與 clean-ROM hash 交叉確認 record
  邊界、終止、換行、變數／姓名／道具插值與 control code；`m20` 只完成靜態 parser
  evidence，runtime sequence 與語境仍待補。
- [x] 對 M1.7 的兩個 font consumer 建立 metadata-only BG0 tilemap cross-check：四個
  destination tile ID 與 screenblock 座標可對齊，並保留 8×16 ink-mask hash、CPU writer
  receipt 與 keyboard input provenance；沒有把 final hash mismatch 誤升格成 identity。
- [x] 建立 `0x080063E0`／`0x0800638C`／`0x0800644C` 的 static Thumb BL callsite index，
  保存 caller／literal pointer／bounded hash metadata；所有 126／10／83 個 caller
  仍標為 `unclassified`，沒有把 pointer geometry 當成 scene role。
- [ ] 在同一個 renderer store stop 同步取得目的 tile hash／BG0 entry，消除 immediate
  post-store 與 final VRAM 的時間差；完成前 `0x005E`／`0x0066` 維持 provisional。
- [x] 建立可重跑 `research/summoners-lineage-decoded.jsonl` 本機輸出與 decoder version；
  M21 private receipt 為 7,553 個 NUL 結尾候選 row，但 6,782 個仍含 unresolved unit，
  其餘也沒有 runtime scene context，全部 `eligible_for_ledger=false`。source text 與
  raw 仍 ignored，不在此階段翻譯。
- [x] 以去重候選 target 做 bounded control／blank-record frequency audit；M22 將 `0x0000`、
  `0xFF70`、`0x0001` 與一般 font-record index 分欄，但未擅自命名 semantic 或 scene role。
- [x] 建立 16×12 font-record static renderer；M23 以已知鍵盤假名確認 MSB-first bit order，
  可在 private／ignored 路徑輸出 PGM 供 OCR／人工 context cross-check，不輸出 source。
- [x] 建立 direct `0x080063E0` static caller candidate decoder；M24 僅保留 46 個 ROM-literal
  caller rows／28 個 distinct targets，仍不賦予 runtime scene role 或 ledger eligibility。
- [x] 將 context-derived glyph candidate 與 confirmed map 分開；M25 審計 `0x000C→ー`、
  `0x00A8→ッ` 的 table slot／record hash／direct target counts，confirmed identity 增量為 0。
- [x] 審計 keyboard punctuation cluster；M26 固定 `0x0006/08/09/0A/0C/0D` 的 layout
  candidate、record metadata 與 direct occurrence counts，confirmed identity 增量仍為 0。
- [x] 建立只供本機閱讀的 provisional overlay decoder；M27 產生 46 個 direct rows，其中
  1 row 暫無 unresolved unit，但仍無 runtime scene proof，不進 ledger。
- [x] 建立 source checksum／duplicate／schema drift audit；M28 對 46 個 private rows 得到
  0 hash mismatch、0 duplicate，但因 0 runtime／eligible row，ledger gate 保持關閉。
- [x] 以 M19 clean keyboard gate 的 BG0/BG1 hash、core renderer 與 static caller 交叉出一條
  `ui-name-entry` candidate（M29）；仍保留 `reader_breakpoint_hit=false`、mapping provisional。
- [x] 對既有 direct target `0x1FA616` 以 M20 parser branch、`0x0000` terminator 與 M23
  private render layout 交叉確認 `0xFF70` 僅代表 line advance（M30）；其他 control、
  general codepage 與 ledger gate 仍關閉。
- [x] 以既有 headless BIOS trace 盤點 39 組 `SWI 0x12` source→VRAM tuples（M31）；
  沒有任何解壓輸出匹配 keyboard tile-1/2，`0x1EB044→0x06004020` 只對應 reset-stage
  hash，故仍是獨立 ROM→VRAM negative，不冒充 keyboard provenance。
- [x] M32 沿 M29 candidate 建立固定 known-screen record-raster／BG0 tilemap cross：
  五個 code unit 的 record hash 與 final image mask `5/5`、BG0 tile entry／tile hash
  `10/10`、BG1 keyboard gate `8/8`；reader breakpoint 與 raw byte-copy 仍分欄為
  false。這只把一條 `ui-name-entry` row 提升為 `glyph_identity_confirmed=5`、
  `eligible_for_ledger=true`，不提升 general codepage 或其他 scene rows。詳見
  [`research/m32-known-screen-raster-row-20260816.md`](research/m32-known-screen-raster-row-20260816.md)。
- [x] 為 M32 eligible row 產生 stable source checksum／record proof，讓
  restore／round-trip 能偵測 ROM、codepage、控制碼或 decoder drift；source text 仍
  只在 private／ignored local table，提交 ledger 不含 `source`。

## 里程碑 2B：最小 zh-TW ledger／回插 POC

- [x] 只在 row-level glyph identity／control／string_id gate 通過後，建立一條 bounded
  `ui-name-entry` private source／working row；M32 已通過 `source_hash`／width／
  control schema，其他候選仍禁止進入 ledger。
- [ ] 以 Wikipedia zh-tw、Bahamut 與其他獨立社群來源核對專有名詞；有分歧時保留
  分歧，不自行造音譯。
- [x] 執行 `restore_translations.rb`／`strip_translations.rb` round-trip，提交檔不含
  `source.text`；M32 另完成 byte-identical no-op BPS apply／hash receipt，但沒有把
  no-op 宣稱成文字回插。
- [ ] 取得 target codepage／encoder 與固定槽位或 relocation policy，完成一個有實際
  文字變更、可重抽取且可產生 BPS 的 bounded reinsertion POC。

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
- [ ] 完成 clean-ROM re-extract、round-trip、BPS／patch hash、core/game tests、
  repository safety；每個穩定里程碑只用 path-limited commit 提交本作。
- [ ] 只發布 patch／ledger／工具與研究結論，不發布 ROM、完整原文或未授權字型。
