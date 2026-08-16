# A9PJ bounded terminology audit（2026-08-16）

這份稽核只處理目前兩條 `known-screen` row 能證明的人名片段，不把未分類的
劇情、地圖／事件、角色、戰鬥候選列誤當成術語表。日文 source、完整候選表與
工作記錄仍只留在本機 ignored/private 路徑。

## 已核對的名稱

| scope | 日文顯示／身份 | 官方 Latin／工作處理 | zh-TW 決策 | 狀態 |
| --- | --- | --- | --- | --- |
| 主角姓名欄位 | `フレイン・K・レスター` | `Fulein.K.Lester`；bounded ledger 暫保留 Latin | 不自行造漢字音譯，保留 `Fulein K. Lester` 作工作名 | `terminology-pending` |
| 姓氏片段 | `レスター` | `Lester` | 目前不替換成無社群共識的漢字譯名 | `terminology-pending` |

這裡的日文身份不是 OCR 推測：M34 已以固定 source pointer、16×12 record mask、
BG0 tilemap 與畫面 mask 交叉確認四個 code unit；本文件只引用該研究的摘要，
不複製 source stream。

## 外部來源與分歧

- [Bandai Namco 官方角色頁](https://www.bandainamcoent.co.jp/cs/list/summonerslinage/chr/index.html)
  列出日文角色名與 `Fulein.K.Lester` image label。
- [Game Watch 發售資料](https://game.watch.impress.co.jp/docs/20030109/samo.htm)
  以日文報導確認本作與主角／家族設定。
- [Bandai Namco 發布資料 PDF](https://www.bandainamcoent.co.jp/corporate/press/namco/48/48-046.pdf)
  提供同一發售時期的官方名稱脈絡。
- [日文社群條目](https://w.atwiki.jp/gcmatome/pages/2979.html)
  作為獨立日文社群交叉來源。

本輪檢索沒有找到能直接核對本作角色的臺灣 Wikipedia 或巴哈姆特條目；既有中文
攻略索引也不足以形成多來源、多數決的繁中人名。依 `AGENTS.md` 的專有名詞政策，
不從日文自行創造「弗／芙／雷斯特」等音譯，也不把官方 Latin 標籤冒充既有
zh-TW 社群譯名。若後續找到多個獨立臺灣社群來源，應在這裡追加分歧與證據，再
決定是否替換工作名。

## 對 ledger 的限制

- M32/M34 的提交 ledger 可以保留 `terminology-pending` 與官方 Latin 工作目標，
  但不可把它宣稱為已核定的臺灣譯名。
- 這份稽核不開啟一般批次翻譯；一般 codepage、控制碼與 scene classification
  仍未完成。
- 人名以外的地名、職業、技能、道具、戰鬥與地圖術語沒有足夠證據，維持未建立。

