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
- [ ] 取得實際 source buffer／DMA 邊界或控制流上的文字 consumer／caller，確認至少一組
  code unit→glyph 關係與控制碼；在此之前 source table／work ledger 維持空白。

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
