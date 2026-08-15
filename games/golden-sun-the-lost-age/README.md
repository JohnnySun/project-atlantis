# 《黃金太陽 失落的時代》漢化工作區

本目錄用於從乾淨日版 ROM 建立可重現的簡體／繁體本地化流程。ROM、舊中文版、抽出的原文及實驗構建只保存在本機，不進入 Git。

## 當前進度

- 日版 Rev.00 基準 ROM 的標頭與多種雜湊已校驗。
- 已定位日版文字的上下文 Huffman 樹、分塊指標和壓縮資料。
- 已無損抽取 **12,772 條**訊息的 12-bit 代碼序列，並建立涵蓋全部 152 個擴展字形的 provisional 日文碼表；全量解碼沒有未映射字符。
- 已找到一份本機既有中文版作為行為參考。它以美版 `AGFE01` 為基礎，重寫了解碼程式，不能作為日版可直接套用的補丁。
- 已用日版原字形和完整碼表完成全部待翻譯文本，建立 11,377 條 `zh-Hans`／`zh-TW` 可審核草稿；全量缺漏審計只剩 19 條明確保留的佔位、鍵盤／字符測試及特殊編碼內容，可翻譯缺漏為 0。
- 已完成資料驅動的 `zh-TW` 技術試作：從多個翻譯 JSONL 重建全套 Huffman 資料、加入 2,570 個繁體中文字形，並替換 11,377 條訊息。
- 較早的試作 ROM 已在 mGBA 0.10.5 成功開機至標誌與姓名輸入畫面；最終全量構建已通過自動驗證，但因測試機鎖屏，仍待重新執行完整運行時 QA。
- **2026-08-15**：依 Wikipedia／社群 wiki 交叉核對，將メアリィ（Mia）、シバ（Sheba）的譯名分別由「米雅」「席芭」統一為「米雅莉」「西芭」（140 筆記錄，13 個翻譯檔案；詳見 `translations/glossary.zh-TW.tsv` 對應條目的日期註記）。
- **2026-08-15**：全語料庫（11,377 條）QA 覆核，修正 155 處跨檔案專有名詞不一致，並與前作 `golden-sun-the-broken-seal` 語料庫核對、修正 2 處跨作品衝突（コロッセオ、錬金じゅつ），另修正一則真正的誤譯（アメン・ラー 召喚被誤植為「拉美西斯」，改為正確的「阿蒙拉」）。
- **2026-08-16**：實機測試回報第二部開場捲軸字幕（`translations/alchemy-and-first-game-recap.draft.jsonl`，id 4484 起）顯示亂碼。查明原因並修復，見下方「開場捲軸字幕亂碼 bug」；同批修正該檔案 id 4486／4487 兩筆譯文內容互換的既有錯誤（非本次亂碼成因，屬獨立發現）。
- **2026-08-16 全量重新構建**：已套用上述指標修復重新構建，通過 `verify_text_delta.rb`（11,377 條）與 BPS 往返校驗（逐位元組 `IDENTICAL`，目標 ROM CRC32 `80eba907`）。

### 開場捲軸字幕亂碼 bug：字型／Huffman 指標仍有未修補的字面量參照（已修復）

實機測試回報第二部開場「はるかむかし……」故事回顧捲軸字幕顯示亂碼，其餘畫面（含選單、對話框等）正常。

原因排查：直接讀取建置後 ROM 在指標重定向後的真實位置渲染該區段字串（id 4484「遙遠的古代」等），點陣資料本身完全正確、清晰可辨——問題不在翻譯內容或字型資料，而在指標修補範圍不完整。掃描原始 ROM 全域比對三個關鍵位址（字型表、Huffman 樹入口、字串分塊指標）的所有字面量參照後發現：字型表位址在原始 ROM 中共有 **3** 處字面量參照（`0x0387f8`、`0x03aa38`、`0x03d144`），Huffman 樹入口位址共有 **2** 處（`0x038578`、`0x03d400`），而先前的 `tools/build_zh_tw_trial.rb` 各自只修補了其中 1 處（`font_pointer_literal`／`huffman_pointer_literal` 為單一位址，非陣列）。開場捲軸字幕顯然是由讀取「另一條」未修補參照的程式路徑渲染，因此仍讀取原始日版 152 字形的舊字型表／舊 Huffman 樹，對照我們寫入的擴展字形 ID（遠超過 152）自然解出錯誤資料，顯示為亂碼；其餘畫面走的是已修補的那條路徑，故正常。

這與第一部 `golden-sun-the-broken-seal` 先前發現的「每個角色兩處字面量參照」屬於同一類問題（見該作 README），差別在於第二部字型表恰好有三處而非兩處。修復：`tools/build_zh_tw_trial.rb` 改為 `font_pointer_literals`／`huffman_pointer_literals`／`text_pointer_literals` 陣列，逐一修補所有已知字面量位置；已重新掃描建置後 ROM 確認全部 6 個位址（3 字型 + 2 Huffman + 1 文字）皆指向新表，並重新完成 `verify_text_delta.rb`與 BPS 往返驗證。第一部同一位址集合已重新核對，原本記錄的兩處字面量即為全部，未發現遺漏。

## 日版文字佈局

| 項目 | ROM offset |
| --- | ---: |
| Huffman 上下文指標入口 | `0x064C3C` |
| 字串分塊指標表 | `0x09CF40` |
| 第一段壓縮文字 | `0x064C4C` |
| 單位元組可變寬字形 | `0x05A8CC` |
| 日文擴展固定寬字形 | `0x05BF8C` |
| 字形圖層選擇表 | `0x05CDCC` |
| 字形渲染函式 | `0x03A890` |
| 訊息數 | `12,772` |

文字分成 50 組：前 49 組各 256 條，最後一組 228 條。

```sh
ruby ../../core/golden-sun/extract-huffman-text-ids.rb \
  --rom roms/base/Ougon_no_Taiyou_Ushinawareshi_Toki_JP_AGFJ01.gba \
  --output research/jp-text-ids.tsv \
  --count 12772 \
  --huffman-pointer-table 0x064c3c \
  --string-pointer-table 0x09cf40
```

日文碼表由 Apple Vision `.accurate` OCR、多句對齊投票、ROM 字形與 BDF 像素比對共同建立。OCR 只作候選證據；碼表仍標記為 provisional，便於後續逐字複核。完整本地解碼工作集可用下列命令重建，輸出已由 `.gitignore` 排除：

```sh
ruby ../../core/golden-sun/decode-text-ids.rb \
  --text-ids research/jp-text-ids.tsv \
  --codepage codepages/ja-extended.tsv \
  --output research/jp-decoded.jsonl
```

在 macOS 上需要重新產生 OCR 候選時，可先把 `render-original-text.rb` 的 PGM 輸出交給 Vision，再將結果與代碼序列對齊。這是研究輔助流程，不是正常構建的必要步驟：

```sh
swift tools/ocr_jp_text.swift research/jp-ocr-all/*.pgm > /tmp/gs2-jp-ocr.tsv
ruby tools/infer_ja_codepage.rb research/jp-text-ids.tsv /tmp/gs2-jp-ocr.tsv
```

推導器與正式解碼器共用 `core/golden-sun/japanese_codepage.rb`，避免兩份基礎假名映射產生分歧。投票結果仍須用原 ROM 字形人工複核後才能修改 `codepages/ja-extended.tsv`。

## `zh-TW` 技術試作

目前替換 11,377 條開機、存檔、資料繼承、密碼轉移、難度選擇、姓名輸入、角色預設名、裝備與道具名稱／說明、怪物／首領名稱、精神力／精靈／召喚名稱、職業、戰鬥與狀態訊息、調查與世界地圖、基礎及詳細選單、精靈管理、設定與資料轉移、商店／旅店／神殿／鍛造服務、托勒比遊戲與戰鬥舞台、鬥技場決賽、戰鬥效果、插值戰鬥訊息、四元素精靈效果、召喚效果說明、序章至海迪亞返鄉結局、通關後支線、精靈教學及元素石碑文本；以下列出代表項目，完整資料見 `translations/*.draft.jsonl`，術語見 `translations/glossary.zh-TW.tsv`：

| ID | 場景 | 試譯 |
| ---: | --- | --- |
| 0 | 無存檔資料 | `(沒有紀錄)`（保留原版 ASCII 括號） |
| 5 | 存檔損毀 | `部分資料已損毀，`／`無法正確復原。` |
| 6 | 從神殿復原 | `要嘗試從神殿`／`復原嗎？` |
| 10 | 遊玩時間標籤 | `遊戲時間` |
| 15 | 新遊戲姓名輸入 | `請輸入你的名字。` |
| 18 | 繼續遊戲 | `請選擇要繼續的紀錄。` |
| 32–33 | 寫入警告 | `處理完成前，請勿`／`關閉電源` |
| 36 | 前作資料繼承 | `要繼承前作《開啟的封印》的`／`通關資料嗎？` |
| 39 | 困難模式 | `要以困難模式開始嗎？`／`(怪物會變得更強)` |
| 58–62 | 戰鬥指令 | `攻擊`／`精神力`／`道具`／`防禦`／`逃跑` |
| 73–74 | 精靈系統 | `精靈`／`召喚` |
| 84–86 | 神殿服務 | `治療中毒`／`驅除惡靈`／`解除詛咒` |
| 102–106 | 資料轉移 | `密碼`／`連接線`／`黃金`／`白銀`／`青銅` |
| 115–123 | 設定介面 | `設定項目`／`精神力快捷鍵`／`文字速度`／`視窗顏色`／`戰鬥鏡頭` |
| 131–1126 | 角色、裝備與道具資料 | 八名角色預設名、記錄回答、武器與防具說明、消耗品、精神力授予物、鍛造材料、關鍵道具、基礎及鍛造裝備名稱與四元素精靈分類；`?`／`???` 佔位內容保留原值 |
| 1128–2261 | 怪物與戰鬥資料 | 怪物／首領名稱、四元素精神力、場景與職業技能、戰鬥道具動作、72 隻元素精靈、召喚、敵方招式及元素攻擊說明；ID 1602、1604 為不完整的 `?` 佔位名稱，原樣保留 |
| 2314–3771 | 遊戲機制與地圖資料 | 場景／職業精神力說明、職業名稱、遭遇與戰鬥結果、狀態說明、迷你遊戲、裝備與道具操作、通用調查、拾取訊息、核心選單及世界地圖地點；ID 3432、3456–3469 為假名字符測試／密碼鍵盤功能符號，原樣保留 |
| 4097–4999 | 選單與商店服務 | 詳細選單、精靈管理、狀態／設定／資料轉移、煉金術與前作回顧、武器／防具／道具／雜貨商店、旅店、神殿、雅拉姆鍛造、肖像除錯標籤及骰子規則 |
| 7–57、5000–5831 | 最終系統與鬥技場文本 | 核心錯誤提示、入隊／精靈／召喚訊息、托勒比抽獎與骰子遊戲、連線及怪物戰鬥舞台、前作調查文本、鬥技場決賽規則／關卡／選手、除錯標籤及遺留寶箱訊息；語言中性或功能性佔位原樣保留 |
| 4647–4669 | 商店與裝備狀態 | `持有金幣`／`售價`／`無法裝備`／`敏捷`／`可以鍛造` |
| 2268–2308 | 戰鬥效果說明 | `恢復全體HP`／`解除幻覺、麻痺、睡眠`／`元素抗性`／`戰鬥不能` |
| 3262–3290 | 插值戰鬥訊息 | `{12}的攻擊力下降{16}點！`／`{12}陷入幻覺！`／`{12}被惡靈附身了！` |
| 2481–2498 | 地元素精靈效果 | `大地屏障`／`降低所有敵人的敏捷`／`HP吸收攻擊`／`石化` |
| 2501–2518 | 水元素精靈效果 | `療癒之水`／`冰沙攻擊`／`封印敵人的精神力`／`絕對零度` |
| 2521–2538 | 火元素精靈效果 | `火神之力`／`爆裂攻擊`／`反擊模式`／`瑪爾斯之力` |
| 2541–2558 | 風元素精靈效果 | `連續攻擊`／`精神力封印`／`死亡宣告`／`暫時休戰` |
| 2561–2593 | 四系召喚效果 | `不滅法老的守護神`／`傳說水龍`／`復仇女神`／`雷神` |
| 5761–5829 | 維納斯燈塔序章 | `我們真的可以／就這樣離開嗎？`；保留羅賓、加西亞、潔絲敏與席芭的動態姓名插值及內部分頁 |
| 5832–5907 | 拉利貝洛守衛 | `就由我來當誘餌吧`／`我可不會留情！`／戰敗後恢復與重新會合分支 |
| 5908–5927 | 半島撤離路線 | 三組沿路守衛、怪物戰後對話，以及保留 `{01}` 分頁的兩組方向提示 |
| 5928–5965 | 碑文與船隻調查 | 保留三個 `{01}` 分頁的碑文、梅娜蒂準備的船、寶珠動力與燈塔點燃事件 |
| 5966–5986 | 半島漂流 | 地震令半島脫離岡瓦納大陸、潔絲敏與斯庫雷塔的漂流對話，以及保留動態姓名插值的同伴牽掛 |
| 5987–6022 | 生還者甦醒 | 亞歷克斯帶眾人找到加西亞與席芭，交代燈塔異變與薩帝羅斯、梅娜蒂戰敗，並保留四名動態角色名插值 |
| 6023–6062 | 燈塔墜落與海嘯 | 席芭說明加西亞相救、眾人發現大陸及海嘯逼近；語言中性的 ID 6052 `???` 保留原值，不計入替換數 |
| 6063–6075 | 海嘯後靠岸 | 保留 `{1E}` 身體檢查選項、斯庫雷塔甦醒、確認半島靠岸及入隊訊息 |
| 6076–6126 | 尋人與入隊分支 | 覆蓋潔絲敏、席芭、斯庫雷塔在不同尋找順序下的全部對話、`{1E}` 選項及動態姓名入隊訊息 |
| 6127–6147 | 亞歷克斯的使命 | 亞歷克斯離島尋船、四座元素燈塔與大東海／大西海方位，以及加西亞、潔絲敏救回家人的旅程動機 |
| 6148–6178 | 席芭的命運 | 席芭同行理由、風元素使身分、朱庇特燈塔所需精神力、讀心術回答分支及序章登陸決定 |
| 6179–6249 | 德里村海嘯後對話 | 村莊與印德拉大陸介紹、海嘯災情、失蹤孩童、瑪德拉／坎德拉寺道路情報、旅店飲食及離村建議分支 |
| 6250–6347 | 坎德拉寺修行與試煉 | 皮波伊會面選項、浮空修行、弟子考核、洞窟旁觀反應、玩家通關、解縛術領取與使用提示、通關後弟子群像、熱鍋反應與可疑牆壁提示 |
| 6348–6386 | 海神祠孩童救援 | 貝查羅反覆拋繩、庫普爾脫困、兩人向隊伍致謝、討論追捕祠內神秘生物，以及因飢餓返村的場景收尾 |
| 6387–6388 | 海神祠內調查 | 與德里村神殿相似的神像，以及亞歷克斯取走祠內資金購船並留下的分頁留言 |
| 6389–6486 | 德里災後收尾 | 孩童返家、村民更新、前往瑪德拉的道路情報，以及亞歷克斯離隊後的完整村莊狀態 |
| 6487–6511 | 印德拉海岸與基朋波線索 | 梅娜蒂留下的船、寶珠機關、基朋波潛入者及封印門調查 |
| 6512–6700 | 瑪德拉襲擊與皮卡德事件 | 占婆劫囚、帕亞亞姆追捕、皮卡德審問與冰之精神力、通往奧瑟尼亞的許可及沉船調查 |
| 6701–6746 | 米卡薩拉與西奧瑟尼亞 | 艾爾斯岩、波比奇、南島及繞行道路情報，並介紹狼人與獸人的傳聞 |
| 6747–6918 | 波比奇滿月夜 | 加拉哈德警告、狼人初遇、滿月村莊狀態、旋風術與旋風石、追蹤獸人、瑪哈會談及透視術祕密 |
| 6919–7079 | 波比奇清晨與艾爾斯岩 | 狼人真相後續、瑪哈對精神力之石的推論、精靈贈禮，以及艾爾斯岩碑文與機關提示 |
| 7080–7120 | 揚皮沙漠追捕 | 瑪德拉追捕隊穿越沙漠、商旅與路人情報，以及接近阿拉弗拉的路線提示 |
| 7121–7462 | 阿拉弗拉與帕亞亞姆 | 海嘯後港鎮、避難居民、帆船與桅杆困境、帕亞亞姆對峙及投降、查烏查母子與瑪德拉交涉 |
| 7463–7962 | 阿拉弗拉戰後至尼利村 | 港鎮重建、牢房探視、宮殿貿易提議與修船嘗試、瑪德拉遭基朋波襲擊、黑水晶與皮卡德追蹤，以及尼利村完整占卜分支 |
| 7963–8552 | 尼利村後續至基朋波儀式結束 | 明古山脈變化、基朋波儀式、皮卡德重逢與雷姆利亞揭密、加彭巴雕像機關、黑水晶回收、契約之室，以及儀式後全村狀態 |
| 8553–9109 | 瑪德拉回訪至雅拉姆童謠 | 卡斯特初遇、皮卡德正式同行、精神力船啟航、南島與魔之海傳聞、動物交換支線、雅拉姆村、桑帕瓦鍛造及三段航線童謠 |
| 9110–9709 | 加拉帕斯至占婆對峙 | 蓋亞瀑布與水之岩線索、伊茲摩大蛇事件、元素之岩揭密、宇受賣獎賞、占婆漁獲危機，以及亞歷克斯、卡斯特與阿加迪奧對峙 |
| 9710–10206 | 阿拉弗拉修船至占婆戰後 | 桅杆修復、帕亞亞姆越獄奪船、占婆寶藏帶來的繁榮與怠惰、婆婆大人召喚怪物、海盜真相與賠償和解，以及三叉戟修復 |
| 10207–10714 | 漩渦航行至雷姆利亞之泉 | 波塞冬戰後入境、古城衰退、皮卡德母親死訊、倫帕與巴比往事、古今地圖揭示世界縮小、海德羅／康薩巴托爭論、研磨術與幸運硬幣；ID 10557–10558 只有動態姓名控制碼，原樣保留 |
| 10715–11381 | 熔岩岩線索至朱庇特燈塔戰後會合 | 赫斯佩里亞與普羅克斯情報、基亞那及阿尼莫斯傳說、薩滿村試煉、重力之玉、朱庇特燈塔伏擊與點火、卡斯特／阿加迪奧決戰、亞歷克斯介入及兩隊會合；ID 10750 為空白字串，原樣保留 |
| 11382–11927 | 孔提戈會合至普羅克斯出發 | 海迪亞人質真相、伊萬與哈莫相認、阿尼莫斯飛翼升空、席芭與斯庫雷塔的身世對話、洛荷大炮、普羅克斯深淵危機及接受瑪爾斯燈塔使命 |
| 11928–12769 | 火星燈塔至海迪亞返鄉 | 卡斯特與阿加迪奧之死、賢者與末日之龍決戰、黃金太陽、普羅克斯告別、通關後人物支線、精靈教學、各地料理與文獻調查、海迪亞返鄉結局及元素石碑；ID 12770–12771 為相同的特殊編碼字串，待確認碼表及運行時用途 |

構建器使用 Fusion Pixel Font 10px Monospaced `v2026.08.11` 的
`fusion-pixel-10px-monospaced-zh_hant.bdf`。`zh_hant` 是上游檔名；Atlantis 的輸出語種仍明確定義為 `zh-TW`，兩者不可混為未指定地區的通用繁體目標。

從專案根目錄執行：

```sh
ruby games/golden-sun-the-lost-age/tools/build_zh_tw_trial.rb \
  --rom games/golden-sun-the-lost-age/roms/base/Ougon_no_Taiyou_Ushinawareshi_Toki_JP_AGFJ01.gba \
  --text-ids games/golden-sun-the-lost-age/research/jp-text-ids.tsv \
  --codepage games/golden-sun-the-lost-age/codepages/ja-extended.tsv \
  --translations games/golden-sun-the-lost-age/translations/system-messages.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/ui-labels.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/character-defaults-and-responses.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/item-descriptions-core.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/item-descriptions-forged.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/item-names-weapons.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/item-names-armor.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/item-names-consumables.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/item-names-forged-weapons.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/item-names-forged-armor.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/item-names-materials-quests.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/item-djinn-categories.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/monster-names.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/psynergy-names-elemental.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/psynergy-names-field-and-class.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/combat-effect-names.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/battle-item-action-names.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/djinn-names.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/summon-names.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/enemy-skills-basic.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/enemy-skills-special.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/enemy-skills-advanced.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/psynergy-descriptions-elemental.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/field-and-class-psynergy-descriptions.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/enemy-skill-descriptions.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/class-names.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/battle-system-messages.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/status-labels-and-help.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/inventory-and-minigame-ui.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/field-inspection-system.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/debug-and-core-ui.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/world-map-locations.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/system-menu-details.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/djinn-management-ui.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/status-config-and-transfer.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/alchemy-and-first-game-recap.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/weapon-shop-dialogue.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/armor-shop-dialogue.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/item-shop-dialogue.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/inn-and-sanctum-dialogue.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/yallam-forge-dialogue.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/general-store-dialogue.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/portrait-debug-labels.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/gambling-dice-rules.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/remaining-core-system.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/tolbi-games-and-battle-stage.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/legacy-inspections-and-colosso.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/colosso-finals-guidance.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/colosso-finals-and-debug.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/legacy-treasure-messages.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/shop-status.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/battle-effects.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/battle-messages.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/djinn-effects.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/summon-effects.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/opening-venus-lighthouse.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/opening-lalivero-guards.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/opening-lalivero-route.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/opening-peninsula.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/opening-drift.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/opening-survivors.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/opening-tsunami.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/opening-landfall.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/opening-party-search.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/opening-alex-mission.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/opening-sheba-destiny.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/deli-tsunami.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/deli-missing-children.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/deli-routes.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/deli-travelers.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/kandorean-gate.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/kandorean-examination.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/kandorean-trial-result.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/kandorean-lash-reward.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/kandorean-lash-receipt.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/kandorean-post-trial.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/kandorean-final-hints.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/sea-god-shrine-rope.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/sea-god-shrine-reunion.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/sea-god-shrine-discovery.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/deli-after-rescue.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/deli-children-home.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/deli-alex-departure.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/deli-post-departure.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/indra-wreck-and-kibombo.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/madra-arrival.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/madra-crisis-rumors.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/madra-piers-interrogation.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/madra-osenia-route.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/mikasalla-west-osenia.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/garoh-werewolf-encounter.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/garoh-full-moon-night.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/garoh-maha-revelation.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/garoh-morning-aftermath.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/garoh-maha-theory.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/garoh-reward-and-airs-rock.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/yampi-madra-pursuit.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/alhafra-arrival.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/alhafra-town-and-port.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/alhafra-pirates.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/alhafra-resolution.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/alhafra-reconstruction.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/alhafra-postgame.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/madra-kibombo-aftermath.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/madra-naribwe-route.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/naribwe-fortune-teller.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/naribwe-kibombo-prelude.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/kibombo-ritual-opening.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/kibombo-lemuria-reveal.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/kibombo-statue-ritual.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/kibombo-contract-aftermath.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/madra-return-karst.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/piers-joins-ship-launch.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/east-sea-islands.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/yallam-song-navigation.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/garapas-aqua-rock.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/izumo-orochi-crisis.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/izumo-orochi-battle.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/izumo-orochi-aftermath.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/izumo-elemental-rock-reveal.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/izumo-reward-departure.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/izumo-departure-champa-arrival.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/champa-payaaym-rumors.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/champa-fishing-crisis.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/champa-alex-reunion.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/champa-karst-agatio-confrontation.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/champa-threat-babi-news.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/alhafra-mast-repair.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/alhafra-payaaym-escape.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/alhafra-ship-theft.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/alhafra-after-ship-theft.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/champa-payaaym-return.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/champa-obaba-confrontation.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/champa-payaaym-reconciliation.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/champa-trident-restoration.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/champa-postgame.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/lemuria-whirlpool-arrival.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/lemuria-entry-and-decline.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/lemuria-town-and-piers-family.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/lemuria-piers-mourning-and-lunpa.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/lemuria-lunpa-babi-alchemy.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/lemuria-hydros-audience.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/lemuria-shrinking-world-debate.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/lemuria-grind-and-departure.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/lemuria-fountain.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/magma-rock-and-contigo-rumors.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/contigo-anemos-heritage.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/shaman-village-arrival.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/shaman-trial-road.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/shaman-trial-battle.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/jupiter-lighthouse-approach.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/jupiter-lighthouse-reunion.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/jupiter-lighthouse-karst-agatio.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/jupiter-lighthouse-rescue.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/jupiter-lighthouse-beacon.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/jupiter-lighthouse-aftermath.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/contigo-reunion-and-truth.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/contigo-hama-and-wings.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/contigo-flight-and-aftermath.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/contigo-ivan-hama-farewell.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/contigo-anemos-and-sheba.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/sheba-kraden-and-loho.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/loho-cannon-and-prox-arrival.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/prox-crisis-and-parents.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/prox-puelle-and-mars-mission.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/prox-mars-departure.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/mars-lighthouse-karst-agatio.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/mars-lighthouse-wise-one.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/mars-lighthouse-doom-dragon.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/mars-lighthouse-parents-and-star.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/golden-sun-and-escape.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/prox-farewell.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/prox-postgame.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/homeward-wise-one-test.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/alex-golden-sun-coliseum.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/coliseum-koulan-thieves.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/thieves-djinn-tutorial.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/venus-djinn-tutorial.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/field-inspections-books.draft.jsonl \
  --translations games/golden-sun-the-lost-age/translations/vale-epilogue-and-tablets.draft.jsonl \
  --bdf games/golden-sun-the-lost-age/research/vendor/fusion-pixel-font-10px-monospaced-bdf-v2026.08.11/fusion-pixel-10px-monospaced-zh_hant.bdf \
  --output games/golden-sun-the-lost-age/roms/build/golden-sun-tla-zh-tw-trial.gba
```

目前的試作資料從 `0xF80000` 寫入 295,516 bytes，指標改為：

| 項目 | 新 GBA pointer | ROM offset |
| --- | ---: | ---: |
| 擴展字型 | `0x08F80000` | `0xF80000` |
| Huffman 表 | `0x08FC806C` | `0xFC806C` |
| 文字表 | `0x08FC80CC` | `0xFC80CC` |

新增字形 ID 已到 `0xBA1`（共 2,570 個），因此構建器使用十二組上下文 Huffman 樹；通用抽取器已從十二組樹完整反解全部 12,772 條訊息。

用通用 BPS 工具產生及重套補丁：

```sh
ruby core/patches/bps_create.rb BASE.gba TRIAL.gba TRIAL.bps
ruby core/patches/bps_apply.rb BASE.gba TRIAL.bps REAPPLIED.gba
```

本次可重現結果：

- 基準 CRC32：`830b795f`
- 試作 CRC32：`63ea7dd4`
- BPS patch CRC32：`eaa04450`
- BPS 大小：295,752 bytes
- 試作與重套 ROM SHA-256：`71456b46642125415ddfdd714934153fef1cfaf15491ce3ec9f3c863bde31bb1`

用新指標重新抽取後，只有 180 個翻譯批次指定的 11,377 個 ID 不同；其餘 1,395 條訊息的 12-bit 代碼序列與來源 TSV 完全一致。構建器會先用碼表反解並核對每筆翻譯記錄的日文原文，避免人工辨識錯誤直接進入 ROM。未替換訊息的全量審計只剩 19 條含日文內容：15 條假名字符測試／密碼鍵盤功能符號、ID 1602、1604 的不完整佔位名稱及 ID 12770–12771 的特殊編碼；這些均有明確保留理由，可翻譯缺漏為 0。

翻譯目標可用大寫 `{HH}` 明確標出已確認的內部控制碼，例如角色名插值 `{12}` 或數值插值 `{16}`。共用解析器會把標記還原為 0x00–0x1F 代碼；構建器要求譯文控制碼的順序與數量和來源完全一致，並同樣核對換行 `{03}`。ID 6345 的 `{09}{02}` 是感嘆詞前的效果選擇前綴與模式值，後方另有獨立的 `{02}` 訊息結束碼；三個單元均原樣保留，具體視聽效果仍待場景 QA。沒有顯式標記的既有短字串仍可繼承來源前後綴控制碼。

## 合規邊界

公開倉庫只保存工具、偏移、雜湊、研究結論及有權分享的翻譯資料。使用者必須自行提供合法 ROM；不發布 ROM、來源不明字型，或可還原大段原作腳本的資料。

詳見 [研究記錄](research/baseline-20260814.md)及[路線圖](ROADMAP.md)。Fusion Pixel Font 的來源與授權記錄見[共用字型說明](../../vendor/fonts/fusion-pixel-font/README.md)。
