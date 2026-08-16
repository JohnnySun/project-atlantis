# 《三國志英傑傳》（三國志英傑伝）本地化工作區

本目錄只處理 GBA 日版《三國志英傑伝》，工作 slug 為
`sangokushi-eiketsuden`。上一輪候選資料曾把《英傑傳》和《孔明傳》合併；本工作區明確不建立、不修改《孔明傳》資料。

本遊戲採用 `docs/TRANSLATION-LEDGER.md` 的原文分離流程：日版 ROM、解出的原文、字型圖片、OCR 結果與工作記錄只留在本機；可提交的 `translations/*.jsonl` 只能保存 `source_hash` 和譯文，不得帶 `source` 原文欄位。

## 當前狀態（2026-08-16）

- **產品識別候選已建立**：公開資料將 GBA 商品標示為 `AGB-P-B3EJ`；`game.yml` 只記錄產品代碼 `B3EJ`，不把它誤當成尚未驗證的 GBA ROM header game code。
- **ROM 偵察尚未開始**：本機工作區、常用下載目錄和掛載卷沒有可讀的 B3EJ／《英傑傳》ROM；委派來源主機的唯讀 SSH 嘗試也因認證失敗，未取得檔案。故目前沒有 CRC32、雜湊、ROM revision、文本偏移或 codepage 結論。
- **公開術語研究已建立**：`translations/glossary.zh-TW.tsv` 是待 ROM 核對的臺灣繁體候選表，涵蓋武將、地名、兵種／官職、策略和戰役事件用語；`research/term-sources.md` 記錄來源交叉核對與爭議項目。
- **沒有翻譯批次**：尚未產生 `research/sangokushi-eiketsuden-decoded.jsonl`，也沒有任何可提交 ledger 記錄；因此不能宣稱已完成劇情翻譯或可逆回插。

## 待取得日版 ROM 後的唯讀偵察順序

1. 將合法自有 dump 放在本機 `roms/`（該路徑已被 Git 忽略），解析 header title、game code、maker code、revision、檔案大小，計算 CRC32／MD5／SHA-1／SHA-256，並與 `B3EJ` 產品候選分開記錄。
2. 以唯讀掃描確認標準 Shift-JIS、候選指標表、GBA 位址範圍、BIOS 解壓縮呼叫與熵區段；每個候選都要記錄偏移和判定理由，不把合法位元組模式直接當成文字。
3. 若靜態結果不足，再以 mGBA／GDB 觀察實際文字渲染、VRAM tile／tilemap、字型搬移和執行期資料。需分開記錄「字型位址已定位」和「glyph identity 已確認」兩種進度。
4. 解出一小段可重現的字串結構後，建立遊戲專用解碼器，輸出本機 `research/sangokushi-eiketsuden-decoded.jsonl`：每行至少含 `string_id`、`locale`、`text`、`provenance`，並標記 confirmed／provisional／unmapped 證據層級。
5. 只從本機原文表透過 `core/ledger/restore_translations.rb` 產生 `work/` 工作記錄；翻譯完成後以 `core/ledger/strip_translations.rb` 產生可提交帳本，再跑 schema、安全檢查、重抽取和回插測試。

## 控制碼、排版與回插邊界

目前尚未知道本作的文字編碼、字型格式、換行／游標控制碼、字串終止符、指標或壓縮格式，因此不套用黃金太陽或光明之魂的任何格式假設。控制碼契約、最大寬度／行數和回插位置，必須等 B3EJ ROM 的實證解碼後寫入本 README 與遊戲專用工具。

## 公開研究的使用限制

公開攻略只用來建立臺灣繁體術語候選、章節／戰場索引和事件分類，不作為日版 ROM 原文或逐句翻譯來源。正式翻譯仍以日版 ROM 解碼結果為準；公開來源的完整腳本、攻略段落和 ROM 均不保存到 Git。

來源與術語決策記錄見 [`research/term-sources.md`](research/term-sources.md)；唯讀偵察帳見 [`research/recon-ledger.md`](research/recon-ledger.md)。
