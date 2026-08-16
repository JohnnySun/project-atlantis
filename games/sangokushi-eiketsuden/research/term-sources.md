# 術語研究來源與決策記錄

## 用途與限制

本文件只支援 `zh-TW` 術語候選、章節／戰場索引和專有名詞的社群慣用字形。它不是日版 ROM 原文表，也不是把外部攻略改寫成翻譯；正式採用前仍要以 B3EJ ROM 的實際字串和畫面上下文核對。

依 `AGENTS.md` 的專有名詞規則，專有名詞至少交叉查看臺灣中文 Wikipedia 與巴哈姆特；日文 GBA 攻略 Wiki 用來確認日文詞形和 GBA 版章節，光榮官方頁只作產品／攻略書背景，不把攻略內容當成可提交原文。

## 使用過的來源

1. [中文 Wikipedia：三國志英傑傳](https://zh.wikipedia.org/wiki/%E4%B8%89%E5%9C%8B%E5%BF%97%E8%8B%B1%E5%82%91%E5%82%B3)（臺灣正體檢視可由頁面語言選單切換）：確認作品名稱、GBA 版本、劉備主角與英傑傳系列範圍。
2. [巴哈姆特：請告訴我 GBA 三國英傑傳的攻略](https://forum.gamer.com.tw/C.php?bsn=1566&snA=155)：確認臺灣玩家使用的武將、戰役、地名與劇情事件字形；頁面本身註明使用繁體中文，內容仍只作術語交叉參考。
3. [巴哈姆特：三國英傑傳奇・序章：汜水關之戰](https://forum.gamer.com.tw/C.php?bsn=1566&snA=649)：確認序章關卡、道具／策略與對話事件的臺灣用字候選。
4. [光榮：三國志英傑伝アドバンスガイド](https://www.gamecity.ne.jp/media/book/game/game_etc/eiketu/adv.htm)：確認官方將本作攻略內容定位為 GBA 版的全流程、道具和策略資料；不擷取其圖片或完整內容。
5. [日文《三國志英傑伝》GBA 攻略 Wiki](https://wikiwiki.jp/rimei/)：確認 GBA 版日文章節、戰場、兵種與策略的原詞索引；網站自稱有志整理，個別內容待 ROM 核對。
6. [日文全體戰場流程](https://wikiwiki.jp/rimei/%E3%82%B7%E3%83%8A%E3%83%AA%E3%82%AA%E6%94%BB%E7%95%A5/%E5%85%A8%E4%BD%93%E3%83%81%E3%83%A3%E3%83%BC%E3%83%88)：建立戰場事件與路線的待核對清單。
7. [公開產品資料中的 B3EJ 型號](https://w.atwiki.jp/yamamura2/pages/3354.html)：只支援 `AGB-P-B3EJ` 產品代碼候選；不能替代 ROM header 或雜湊證據。
8. [GameHacking：Sangokushi Eiketsuden GBA 資料](https://gamehacking.org/game/5844)：作為外部 CRC32／4 MiB／`AGB-B3EJ-JPN` 交叉核對；不保存其 ROM 或完整資料，也不把單一資料庫頁面當成翻譯來源。
9. [日文 GBA 攻略 Wiki：夷陵の戦い](https://wikiwiki.jp/rimei/%E3%82%B7%E3%83%8A%E3%83%AA%E3%82%AA%E6%94%BB%E7%95%A5/%E4%B8%89%E7%AB%A0/%E4%BA%94%E5%B9%95%E3%80%80%E8%9C%80%E6%BC%A2%E5%BB%BA%E5%9B%BD/%E5%A4%B7%E9%99%B5%E3%81%AE%E6%88%A6%E3%81%84)：交叉核對夷陵戰與劉備生死造成結局流程差異；只作 E pool 的已知流程背景，不作逐句 source。
10. [系列流程整理：三國志英傑伝](https://w.atwiki.jp/sfcall/pages/968.html)：交叉核對史實／假想結局與劉備、關羽生死差異；平台是系列參考，不能替代 B3EJ GBA runtime。
11. [中文 Wikipedia：蜀漢](https://zh.wikipedia.org/wiki/%E8%9C%80%E6%B1%89) 與 [諸葛亮](https://zh.wikipedia.org/wiki/%E8%AF%B8%E8%91%9B%E4%BA%AE)：確認 `蜀`、`漢朝`、`劉備`、`諸葛亮／孔明` 的臺灣歷史／三國志字形；仍與巴哈姆特／GBA Wiki 交叉使用。

12. [中文 Wikipedia：桃園三結義](https://zh.wikipedia.org/wiki/%E6%A1%83%E5%9C%92%E4%B8%89%E7%B5%90%E7%BE%A9) 與 [巴哈姆特：桃園三結義](https://forum.gamer.com.tw/C.php?bsn=36815&snA=1925)：交叉確認 `桃園`、`桃園三結義`／`桃園結義` 為臺灣三國題材常用字形；只作 E:009／E:010 的專有名詞決策，不作日版 ROM 原文來源。
13. [中文 Wikipedia：漢獻帝](https://zh.wikipedia.org/wiki/%E6%B1%89%E7%8C%AE%E5%B8%9D) 與 [巴哈姆特：獻帝相關三國志討論](https://forum.gamer.com.tw/G2.php?bsn=6331&lorder=5&parent=1584&sn=600)：交叉確認日文 `献帝` 對應臺灣慣用 `獻帝`；只作 E:012 的人物術語決策，不作日版 ROM 原文來源。

## 暫定決策

- 中國歷史人物與常見地名優先使用臺灣三國志慣用繁體字：例如 `劉備`、`關羽`、`張飛`、`曹操`、`孫權`、`諸葛亮`、`趙雲`、`黃忠`、`魏延`、`龐統`、`司馬懿`、`陸遜`、`洛陽`、`長安`、`徐州`、`襄陽`、`成都`、`漢中`。
- story-event E batch 1 的 `蜀`／`劉備` 沿用上述臺灣三國志慣用字形；以中文 Wikipedia 與巴哈姆特來源交叉支持，`命運`、`日後`、`何去何方` 是普通敘事用語，不新增自造專有名詞。這批的 `zh-TW` 先保持 `ai_review`，仍須 B3EJ 畫面語境與人工終審。
- story-event E batch 2 的 `漢朝` 沿用臺灣歷史／三國志常用朝代字形；仍以中文 Wikipedia 與巴哈姆特的既有三國題材用字作交叉背景，正式採用保持 `ai_review`，待 B3EJ 結局畫面核對。
- story-event E batch 3 的 `劉備`、`孔明`、`趙雲`、`魏` 沿用多來源臺灣三國志字形；`孔明` 是諸葛亮的字，故 glossary 保留別稱欄位。夷陵／史實結局流程與 E 的 hash-only record 分組相符，標記為 `provisional-known-screen-cross`，不升格為自然 runtime 證據。
- E batch 3 的 `等`、`卻`、`國` 使用獨立 E-specific licensed glyph map；這是字型／codepage 工程決策，不把 raw unit addressing 當成 Unicode identity，也不沿用與 E source overlap 的四池 mapping。
- story-event E batch 4 的 `吳` 採臺灣三國志常用繁體字形，與 `孫吳`／`吳國` 的 Wikipedia、巴哈姆特和 GBA 攻略用字一致；它使用 E-specific licensed glyph map，仍保持 `ai_review`。
- story-event E batch 5 延續同一結局分支的 `吳`／`蜀`／`魏`／`漢朝` 用字；`從此`、`只能臣服`、`復興`、`夢想` 是普通敘事語，不新增專有名詞。四個新增字形使用 E-specific licensed glyph map，ledger 仍保持 `ai_review`，待自然結局畫面與人工終審。
- story-event E batch 6 延續 `劉備`、`孔明`、`張飛`、`關羽`、`蜀`、`魏`、`吳` 的既有臺灣三國志字形；`關` 的 raw-unit slot 是 E-specific 字型工程決策，不由 addressing 推導 Unicode identity。兩筆 ledger 維持 `ai_review`，待自然結局畫面與人工終審。
- story-event E batch 7 的 `桃園`／`桃園結義` 沿用臺灣三國題材的主流字形；Wikipedia 與巴哈姆特交叉支持，且只把日文 `桃園の誓い` 對應為術語候選，不把典故來源當成 B3EJ 逐句翻譯證據。E:009／E:010 維持 `ai_review`，待自然結局畫面與人工終審。
- story-event E batch 8 的 `献帝` 採臺灣慣用 `獻帝`；Wikipedia 與巴哈姆特交叉支持。`亂世` 是普通敘事語，不新增自造專有名詞；E:012／E:013 維持 `ai_review`，待自然結局畫面與人工終審。
- story-event E batch 10 的 `魏`、`蜀漢` 沿用臺灣三國史／三國志慣用國號；`司馬一族` 是描述司馬氏家族的普通敘事詞，保留直譯並標為 provisional，不把它升格成單一人物專名。E:016／E:017 維持 `ai_review`，待自然結局畫面與人工終審。
- story-event E batch 11 的 `獻帝` 沿用 Wikipedia／巴哈姆特交叉支持的臺灣字形；`漢朝`、`皇帝`、`玉璽` 是歷史／三國題材常用詞，不新增自造專有名詞。E:018／E:019 維持 `ai_review`，待自然結局畫面與人工終審。
- story-event E batch 12 延續 `漢朝`、`玉璽`、`獻帝`、`劉備`、`魏` 的既有臺灣三國志字形；`民心`、`領袖`、`衰退` 是普通敘事用語，不新增專有名詞。E:020／E:021 維持 `ai_review`，待自然結局畫面與人工終審。
- story-event E batch 13 延續 `劉備`、`獻帝`、`魏` 的既有臺灣三國志字形；`重用`、`叛亂`、`地位` 是普通政治／歷史敘事用語，不新增專有名詞。E:022／E:023 維持 `ai_review`，待自然結局畫面與人工終審。
- 日文 `策略` 保留為遊戲系統類別，不先改成泛稱「技能」；各策略名稱另在 glossary 以效果／類別記錄，待 ROM 選單上下文確認。
- 日文 `兵種` 在研究文件中譯為「兵種」；`短兵`、`長兵`、`弓兵`、`輕騎兵`、`重騎兵`、`武道家`、`軍樂隊`、`猛獸師`、`妖術使`、`輸送隊` 等候選保留其三國題材慣用語感。
- `汜水關`、`雒`、`葭萌關`、`瓦口關`、`天蕩山`、`麥城`、`西陵`、`夷陵` 等地名先採社群常見繁體字；若 ROM 畫面或多個獨立來源出現分歧，保留爭議並不自行創造音譯。
- 日文 `発石車` 與臺灣攻略常見的「投石車／發石車」存在字形差異；glossary 先標為 `投石車`、status `provisional`，必須用 ROM 兵種選單確認後才可升級。
- `一騎打ち` 統一候選為 `單挑`，`援軍`、`増援` 分別候選為 `援軍`、`增援`，`説得` 先候選為 `說服`；這些是事件用語，不代表任何尚未抽出的原文句子。

## 術語表狀態

`translations/glossary.zh-TW.tsv` 的 `provisional` 表示「公開來源支持但尚未以 B3EJ ROM 畫面／上下文核對」，不是已核准翻譯。`unresolved` 表示來源或字形有分歧；沒有足夠 ROM 證據前不強行消除分歧。

本機 ROM 的 SHA-256 與其他雜湊以 `research/recon-ledger.md` 的 ROM receipt 為準；外部 CRC 只作一致性線索。header complement 的 stored／calculated mismatch 已保留，不因外部頁面而修補 dump。
