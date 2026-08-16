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
- 一份 GBA 英文操作／攻略整理明確記錄 title screen 的 START→main menu、GBA 版新增
  選單與戰役事件類型；它只用來校準導航假設與畫面類別，不作日版 ROM 原文或逐句
  翻譯來源：[GameFAQs GBA guide](https://gamefaqs.gamespot.com/gba/925912-san-goku-shi-eiketsuden/faqs/38912)。
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

依 bounded source 的 ID／長度／LF metadata 與已提交 ledger 的批次上下文，E 可分為：
E:000–001 的劉備晚年／桃園結義收束片段、E:002／E:011 的短問題／分支銜接片段、
E:003–010 的夷陵／結局延續片段、E:012–015 的另一結局／夷陵衝突片段、E:016–023
的漢朝復興與政治轉折片段、E:024–031 的漢朝衰退／恢復威勢片段，以及 E:032 的收束
結局片段。這些是 hash-only record metadata 與 bounded ledger 的流程分組，沒有把
日文 payload 寫入本文件；它們與公開攻略所述的「夷陵／劉備生死會影響結局」一致，
因此狀態維持 `provisional-known-screen-cross`，不是 `confirmed-runtime`。

## Known-screen / codepage / layout cross-check

這個 gate 分開記錄流程語意、codepage addressing、Unicode identity 和 runtime reachability：

| 證據面 | bounded 結果 | 狀態與限制 |
|---|---|---|
| known-screen flow | 公開 GBA／系列資料的夷陵、生死分支與 E hash-only 分組相符；E:000–032 全部已有 source-free record ledger | `provisional-known-screen-cross`；未把外部流程當成 ROM 原文或自然畫面 hit |
| record structure | E 33/33 strict Shift-JIS、32/33 LF、0 opaque controls；每個已翻譯 record 保留 LF/control signature、固定槽位與 conservative line budget | `confirmed-static / bounded-layout`；字符數 gate 不是 GBA pixel-width 證明 |
| codepage addressing | common writer path `0x080650A4` lookup → `0x080650DC` expander；codepage file table `0x024110C` 有 1834 entries；E existing-codepage rows 與 E-specific map rows 各自通過 codepage／plane gate | `confirmed-static / bounded-cross`；E-specific 12 slots 的 Unicode identity 來自授權 mapping，不由 raw addressing 推導 |
| runtime glyph pool | B[0] controlled receipt 已確認 common writer、cache `0x02000000`、VRAM/tilemap edge，且 `0x9594→U+90E8` 有 static＋controlled identity | `confirmed-controlled` 但不是 E natural receipt；E natural formatter／cache／VRAM 仍 pending |
| Unicode identity | `劉備`、`孔明`、`趙雲`、`魏`、`獻帝`、`桃園結義` 等採多來源 zh-TW glossary；custom E slot 另有 licensed map／plane hash | `provisional/confirmed-static-by-map`；不把 glyph address 當成 Unicode proof |

## 已確認與未確認

| 證據 | 狀態 | 限制 |
|---|---|---|
| E pointer boundary／static consumer | `confirmed-static` | 函式與 literal 已由遊戲專用 analyzer 驗證 |
| 結局／分支流程分類 | `provisional-known-screen-cross` | 外部攻略與 E 的 hash-only 分組相符，但尚未在畫面看到特定 E entry |
| E:000–E:032 固定槽位回插 | `confirmed-static / bounded` | 18 個 source-free story batches 全部有 fixed-slot／re-extract／BPS receipt；不代表自然可達 |
| 控制碼／版面 | `confirmed-static / bounded-layout` | 33 records 的 LF/control signatures 與各批 audit receipt；pixel width、文字框座標仍未量測 |
| common codepage | `confirmed-static / controlled-cross` | codepage table、lookup／expander chain 與 B[0] 的 U+90E8 controlled receipt 相符；不把它升格為 E natural glyph identity |
| E formatter→glyph cache→VRAM/tilemap | `unknown / runtime-pending` | 目前只有與既有 writer 的靜態相接；沒有自然 runtime hit |
| Unicode identity | `provisional / bounded-static-by-map` | 主流人物／地名依多來源術語表；E-specific custom units 依授權 map／plane gate；不由 raw addressing 推導 |

下一個自然 runtime 嘗試只能在確認本 session 自有 mGBA listener／process 後進行；M2.5
已確認 startup→stable-title 與 input timing，但 START／A 的 stable-title path 仍未
跨 state gate。若後續 transport 或遊戲 state gate 仍不提供自然 hit，繼續記錄 negative，
不把已知流程交叉證據升格成 runtime receipt。
