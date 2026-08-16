# A9PJ 日文 source table 規格（2026-08-16）

這份文件定義 source table 的安全輸入與審核門檻，不是原文表本身。`source.text` 只能
由研究者在本機以合法 A9PJ ROM 重新產生；任何 `*-decoded.jsonl` 與 `work/` 檔案都
留在 `.gitignore` 路徑，不進 Git。

## 本機 row contract

真正完成 decoder 後，`research/summoners-lineage-decoded.jsonl` 每行至少要有：

```json
{"string_id":"<stable-id>","locale":"ja","text":"<local-only>","provenance":"<rom-hash;offsets;decoder-version>"}
```

`string_id` 必須由可重跑的 pointer／record 幾何產生，不能用抽取順序暫代。`provenance`
至少記錄 A9PJ ROM SHA-256、來源 file offset 或 pointer table、字串終止邊界、decoder
version，以及是否有 runtime context。控制碼在寫入 source table 前要正規化成帳本規定的
大寫 `{HH}` 形式；若某個 code unit 尚未能分辨成字元或控制碼，該 row 不得進入翻譯批次。

## 建立 row 的必要證據

每一條 source row 必須同時具備：

1. 原 ROM 的來源指標／record 與可重跑的 file offset。
2. 明確的 halfword／byte 邊界、終止碼、換行與插值／控制碼消費規則。
3. code unit 到 glyph 的定位證據，並把「能定位 glyph」和「知道 glyph 身分」分開記錄。
4. 至少一個獨立交叉證據：runtime consumer、控制流引用、或與畫面／tilemap 對應的
   可重現結果。單純 16-bit NUL 統計、合法指標或外部 patch bytes 都不夠。
5. 若 row 的語境標成事件、選單、角色或戰鬥，必須記錄該分類的判定依據；不能把
   候選區內所有 NUL 結尾資料自動當成劇本。

## 帳本接線

達到上述門檻後，流程固定為：

```text
clean A9PJ -> game decoder -> research/summoners-lineage-decoded.jsonl (local only)
                                      |
                                      v
translations/<batch>.jsonl (source_hash only, commit-safe)
                                      |
                                      v
restore_translations.rb -> work/<batch>.jsonl (local only)
                                      |
                                      v
strip_translations.rb -> translations/<batch>.jsonl
```

第一批只允許少量、已確認語境的短句／UI 字串；在碼頁、控制碼、長度限制與回插 round
trip 完成前，不建立 `translations/*.jsonl` 記錄，不從英文／中文 patch 反推日文，也不
把猜測放進 `review_notes`。

## 目前狀態

截至本次 M1 bounded capture，尚未有任何 row 通過必要證據：23901 read watchpoint 沒有
取得 stop packet，故沒有 runtime consumer、實際 code unit 序列或 glyph 搬移可供 source
table 使用。source table 目前只有本規格，尚未生成 `*-decoded.jsonl`；work ledger 維持
空白是刻意的安全狀態，不代表翻譯已開始。
