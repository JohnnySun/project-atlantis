# 本地化工作管線

```text
合法原始 ROM／原案
        ↓
遊戲專用抽取器 ──→ 原文記錄 + 場景／指標／控制碼
        ↓
術語預處理與 AI 候選翻譯
        ↓
人工審核 ──→ zh-Hans / zh-Hant
        ↓
字形覆蓋、長度、控制碼與一致性 QA
        ↓
遊戲專用編碼、字庫生成與回插
        ↓
可重現 ROM / BPS（ROM 僅在本機）
        ↓
模擬器與實機回歸
```

## 建議字串記錄

每條記錄至少包含：

- `game`、`revision`、`string_id`
- `source_locale`、`source_text`
- `zh_hans`、`zh_hant`
- `context`、`speaker`、`scene`
- `control_codes`、`max_width`、`max_lines`
- `terms`、`status`、`review_notes`
- `provenance`：原案版本、人工或模型產生方式

交換格式會在黃金太陽碼頁解出後，以實際控制碼和排版需求定稿。原始抽取文本預設不提交，允許分享的翻譯資料則依遊戲和來源逐項決定。

## 翻譯狀態

`untranslated → ai_draft → human_review → in_game_qa → approved`

任何自動重譯都不得覆蓋 `human_review` 或 `approved`；新結果應成為可比較的候選版本。

## 簡繁策略

- 共用語義和上下文，但分開保存成文結果。
- 人名、地名與系列既有譯名由術語庫決定，不交給字符轉換器猜測。
- 繁體版本必須單獨進行字寬、缺字和標點 QA。
- 轉換工具只作初稿，所有差異都保留來源與審核狀態。

## 字庫來源與子集

- 8／10／12px 的主要候選來自 `vendor/fonts/fusion-pixel-font`。
- 簡體、台灣繁體、香港繁體和傳統印刷字形參考
  `vendor/fonts/ark-pixel-font` 的語言特定版本。
- 16×16 覆蓋後備來自 `vendor/fonts/unifont`；優先比較標準版與
  Unicode T-source 中文版，不直接假定同一字形適合所有地區。
- 每個遊戲只從已核准文本抽取所需 Unicode 字符，產生最小字庫、缺字報告、
  字形來源清單與映射；簡體和繁體必須分開生成與驗證。
- 衍生字庫必須保留其上游授權與來源記錄。
