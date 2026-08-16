# A9PJ zh-TW terminology matrix boundary（2026-08-16）

這是術語審核矩陣，不是 source table，也不是翻譯 ledger。日文欄只列短名稱與
驗證用的專有名詞；完整日文 script、ROM 與 work rows 仍在 ignored／private。所有
尚無臺灣主流共識的名稱保留 `pending`，不自行造漢字音譯。

## 來源規則

- [Bandai Namco 官方角色頁](https://www.bandainamcoent.co.jp/cs/list/summonerslinage/chr/index.html)：
  日文角色名、設定與官方 image-label Latin。
- [巴哈姆特 GNN 臺灣報導](https://gnn.gamer.com.tw/detail.php?sn=8364)：本作在臺灣
  語境的標題／人名寫法交叉；目前能直接確認 `Fulein Lester`。
- [巴哈姆特《幻想傳奇》專題](https://gnn.gamer.com.tw/detail.php?sn=73226)：前作
  角色與世界觀的臺灣慣用語境，僅用來核對跨作沿用名，不反推本作未出現的譯名。
- [臺灣玩家論壇的《世界傳奇》角色譯名表](https://www.games.idv.tw/viewtopic.php?t=11888)：
  `クラース` 的社群寫法交叉；與其他中文來源不一致時保留分歧。
- [Wikipedia《幻想傳奇》](https://zh.wikipedia.org/wiki/%E5%B9%BB%E6%83%B3%E5%82%B3%E5%A5%87)：
  系列／前作中文標題背景，不作本作角色漢字名的唯一依據。
- [Newwise 本作攻略](https://www.newwise.com/gonglue/gba/200610/2717.html)：只作
  簡中社群的日文角色表／故事語境旁證，不直接採為 zh-TW 譯名；頁面不是臺灣來源，
  且與官方 Latin 可能不一致。

## 矩陣

| 類別 | 日文／官方 Latin | 目前 zh-TW 工作值 | 狀態與理由 |
| --- | --- | --- | --- |
| 主角 | `フレイン・K・レスター` / `Fulein.K.Lester` | `Fulein`／`Lester` | `confirmed-bounded`：官方 image label 與臺灣 GNN 均採 Latin；不自行造漢字音譯 |
| 人工生命體 | `マカロン` / `Macaron` | `Macaron` | `official-latin-pending-zh-TW`：官方 Latin 已證；「馬卡龍」目前只有非獨立／非臺灣主流旁證，暫不定案 |
| 前作祖先 | `クラース・F・レスター` / `Klarth` | `pending` | 臺灣玩家來源見 `古拉斯`，其他中文來源見 `克拉斯`，存在分歧；不把其中一個冒充多數 |
| 人工生命體／魔王 | `魔王ゼクス` | `pending` | 官方日文頁有角色與設定，但未找到足夠臺灣主流漢字名；保留日文／Latin research key |
| 研究者 | `ガレル` | `pending` | 官方日文頁確認角色語境；未取得兩個獨立臺灣來源的共同中文名 |
| 雙胞胎姊姊 | `ベルガ・モントール` | `pending` | 官方日文頁確認角色／職業；未取得臺灣主流中文名 |
| 雙胞胎弟弟 | `ボルガ・モントール` | `pending` | 官方日文頁確認角色／職業；未取得臺灣主流中文名 |
| 劍士 | `マーク・ギニール` | `pending` | 官方日文頁確認角色／職業；未取得臺灣主流中文名 |
| 系列／前作 | `テイルズ オブ ファンタジア` | `時空幻境／幻想傳奇` | `cross-source-existing`：臺灣系列來源並存；本作劇情專名沿既有官方／社群名稱，不自行改寫 |
| 本作標題 | `サモナーズ リネージ` | `召喚士的血統` | `working-title`：沿本作既有資料夾／臺灣資料用法；不把簡中「召喚者之血統」當 zh-TW 定案 |
| 核心道具 | `契約の指輪` | `契約戒指` | `translation-candidate`：遊戲語境與社群旁證一致；等實際 source row／版面 gate 後才進 ledger |

## 官方系統／職業詞（research-only）

官方產品頁明示下列短詞，但目前沒有把它們和 A9PJ 的 non-UI source row、code-unit
sequence 或版面 receipt 對上；因此它們只是術語準備，不是可提交翻譯：

| 類別 | 日文 | zh-TW 工作候選 | 狀態 |
| --- | --- | --- | --- |
| 系統／單位 | `ユニット` | `單位` | `candidate-awaiting-source-row` |
| 系統／召喚 | `召喚術`／`召喚士` | `召喚術`／`召喚士` | `candidate-existing-term` |
| 成長道具 | `遺品` | `遺物` | `candidate-awaiting-community-check` |
| 成長系統 | `クラスチェンジ` | `轉職` | `candidate-awaiting-layout-check` |
| 職業 | `サモナー` | `召喚士` | `candidate-existing-term` |
| 職業 | `モンク` | `武僧` | `candidate-awaiting-community-check` |
| 職業 | `マジシャン` | `魔法師` | `candidate-awaiting-community-check` |
| 職業 | `ファイター` | `戰士` | `candidate-awaiting-community-check` |
| 職業／角色 | `ルシファー` | `路西法` | `candidate-awaiting-community-check` |
| 職業 | `シャーマン` | `薩滿` | `candidate-awaiting-community-check` |

## 採用規則與下一步

目前只有主角 given-name／surname 的 bounded ledger target 已依官方／臺灣來源核准
為 Latin；其他角色、地名、職業、技能、道具與戰鬥術語仍是 `pending`、
`translation-candidate` 或上面的 `research-only`。官方詞仍需先和 private non-UI
source row 對照，再附上日文 source hash、
scene role、外部依據與寬度預算，再由 `strip_translations.rb` 產生不含 source 的
tracked row。沒有兩個獨立臺灣來源形成合理共識時，保留現有 Latin／日文 key，不強行
音譯。
