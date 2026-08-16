# M3 劇情結局池 E 已知流程交叉證據（2026-08-16）

本文件只記錄公開攻略／作品資料與本機 bounded static metadata 的交叉結果，不保存
ROM、完整日文、攻略原文、圖片或 runtime dump。它把「已知結局流程」與「自然
formatter→glyph→VRAM 收據」分開；前者不能取代後者。

## 外部來源與可核對範圍

- 日文 GBA 攻略 Wiki 將本作標為 GBA 版資料，並將流程分成蜀漢建國、夷陵等章節；
  [三國志英傑伝攻略 Wiki](https://wikiwiki.jp/rimei/)。
- 該 Wiki 的夷陵戰頁記錄：若劉備在該戰倒下，後續會進入符合史實的結局；同頁也列出
  夷陵後仍有分支。這支持 E pool 是結局／分支文字的獨立候選，不能當作 ROM 字串
  逐句來源：[夷陵の戦い](https://wikiwiki.jp/rimei/%E3%82%B7%E3%83%8A%E3%83%AA%E3%82%AA%E6%94%BB%E7%95%A5/%E4%B8%89%E7%AB%A0/%E4%BA%94%E5%B9%95%E3%80%80%E8%9C%80%E6%BC%A2%E5%BB%BA%E5%9B%BD/%E5%A4%B7%E9%99%B5%E3%81%AE%E6%88%A6%E3%81%84)。
- 另一份系列整理將《英傑伝》的結局概括為史實／假想路線，並指出劉備、關羽生死
  會造成結局差異；這是獨立的流程背景，不用來替代本作 GBA source table：
  [三國志英傑伝（SFC 制覇まとめ）](https://w.atwiki.jp/sfcall/pages/968.html)。
- 臺灣用字以中文 Wikipedia 的蜀漢、劉備、諸葛亮條目和既有巴哈姆特來源交叉建立；
  這些來源只用於專有名詞，不把外部敘事當翻譯原文。

## 與本機 E pool 的對照

`analyze_story_pool.py` 對 E `0x0CDB64/33` 的 metadata 是 33 個 unique targets、
32/33 含 LF、33/33 strict Shift-JIS、0 opaque controls；pointer table、target
offset、record source hash 皆已各自做 hash-only receipt。E 的 static chain 為：

```text
table E 0x080CDB64
  → pair helper 0x08011904
  → writer helper 0x080118C8
  → text writer 0x0800CAD8
```

依 bounded source 的 ID／長度／LF metadata，E:002 是短問題句；E:003–E:008 是其後
一條四行結局敘事的連續 records；E:011 與 E:032 則屬其它結局敘事分支的短問題／收束
record。這個分組是 source table 的本機語意分類，沒有把日文 payload 寫入本文件。
它與公開攻略所述的「夷陵／劉備生死會影響結局」一致，因此狀態可升為
`provisional-known-screen-cross`，不是 `confirmed-runtime`。

## 已確認與未確認

| 證據 | 狀態 | 限制 |
|---|---|---|
| E pointer boundary／static consumer | `confirmed-static` | 函式與 literal 已由遊戲專用 analyzer 驗證 |
| 結局／分支流程分類 | `provisional-known-screen-cross` | 外部攻略與 E 的 hash-only 分組相符，但尚未在畫面看到特定 E entry |
| E003／E004 固定槽位回插 | `confirmed-static / bounded` | 另見 batch 3 receipt；不代表自然可達 |
| E formatter→glyph cache→VRAM/tilemap | `unknown / runtime-pending` | 目前只有與既有 writer 的靜態相接；沒有自然 runtime hit |
| Unicode identity | `provisional` | `劉備`、`孔明`、`趙雲`、`魏` 等依多來源術語表；不由 raw addressing 推導 |

下一個自然 runtime 嘗試只能在確認本 session 自有 mGBA listener／process 後進行；若
transport 仍不可用，繼續記錄 negative，不把已知流程交叉證據升格成 runtime receipt。
