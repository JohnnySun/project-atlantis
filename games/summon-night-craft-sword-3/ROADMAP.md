# B3CJ 翻譯與逆向路線圖

狀態標記以可重現證據為準；`[~]` 表示部分完成，`[ ]` 表示尚未完成。

## M0：工作區與來源邊界

- [x] 只建立 `games/summon-night-craft-sword-3/` 內的 `game.yml`、README、ROADMAP、研究帳本與唯讀工具。
- [x] 登錄 B3CJ、容量、CRC、header checksum、公開 SHA-1，並保留外部候選與本機 readback 的區分。
- [x] 定義 `research` 原文表、`work` 工作檔與 `translations` 可提交 ledger 的分工。
- [x] 取得使用者提供的日版 ZIP，唯讀抽出單一 ROM 到 ignored `roms/base/`；未把 ROM 或 ZIP 納入 Git。

## M1：ROM 身分與唯讀偵察

- [x] 用 `tools/inspect_rom.py --strict` 確認 header title、game code、maker code、revision byte 與 header checksum。
- [x] 記錄本機 size、CRC32、MD5、SHA-1、SHA-256；與外部候選值分開保存。
- [x] 用 `tools/scan_static.py` 對 halfword-aligned Shift-JIS-shaped run、指標 run 與有界 LZ77／RLE decoder candidate 做掃描。
- [~] 壓縮／指標候選仍只有靜態證據；mGBA scripting/headless 路徑受 CLI 能力限制，未把候選升格為文本或資料表結論。

本里程碑的靜態報告只保留 offset、長度、計數、引用與 hash。共用 `core/gba` client／capture／renderer 的 6 項測試已通過；一次性的 mGBA boot snapshot 已記在研究帳本，但 B3CJ capture 仍受其他 session 的 2345 與 alternate-port listener 阻塞，不再重試 port shim，也不把 runtime 實驗工具納入本作工具集。

## M2：文本與字型格式

- [ ] 定位劇情／支線／夥伴／鍛造／戰鬥／道具的字串儲存區與邊界。
- [ ] 判定文本是否直接編碼、使用自訂 codepage、壓縮、腳本 bytecode 或混合格式。
- [ ] 定位字型資料與渲染器；分開驗證 glyph addressing 與 glyph identity。
- [ ] 確認字串 ID、指標、換行、控制碼、字寬／行數上限與未修改內容的回插契約。
- [ ] 以 ROM-to-VRAM byte match、已知畫面內容或全語料庫上下文重讀交叉確認解碼。

## M3：原文表與可逆試驗

- [ ] 由遊戲專用 decoder 產生本機 `research/summon-night-craft-sword-3-decoded.jsonl`，每行含 `string_id`、`locale`、`text`、`provenance`。
- [ ] 先選一個可達、短且有明確結構的 UI／道具／戰鬥批次，不一次處理全遊戲。
- [ ] 建立本機 `work/*.jsonl`，明寫 `zh-Hans`、`zh-TW`、`status`、`context`、`terms`。
- [ ] 用 `core/ledger/restore_translations.rb` 與 `strip_translations.rb` 驗證 source hash 與帳本往返。
- [ ] 只提交不帶 `source` 的 `translations/*.jsonl`，並通過 `scripts/check-repository-safety.rb`。

## M4：有限量翻譯與術語

- [ ] 依日文原文與上下文建立劇情、支線、夥伴、鍛造、戰鬥、道具的分批工作帳。
- [ ] 專有名詞以 Wikipedia zh-tw、巴哈姆特及其他獨立社群資料交叉核對；不把單一 patch 的譯名視為定論。
- [ ] 建立 `translations/glossary.zh-TW.tsv`（只收已核對術語，不放完整原文段落）。
- [ ] 逐批做字寬、行數、缺字、控制碼、簡繁混用與用語一致性 QA。

## M5：回插、BPS 與 runtime QA

- [ ] 建立本作專用 encoder／font subset／回插器；缺字、來源 hash、控制碼與長度不符時 fail closed。
- [ ] 從重建 ROM 重新抽取，確認未修改字串與目標翻譯均吻合。
- [ ] 生成 BPS，套用後做 byte-for-byte round-trip，記錄 target CRC32、patch size、SHA-256。
- [ ] 以 mGBA 測試實際可達的劇情／支線／夥伴／鍛造／戰鬥／道具畫面，保留未測試範圍。
- [ ] 只有完成上述收據後，才評估 zh-Hans／zh-TW 發布。
