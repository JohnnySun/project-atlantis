# M2 帳本／控制標記 bounded 邊界（2026-08-16）

## 目的

把本機 ignored 的 strict source table 轉成可提交、但不含原文的 ledger
scaffold，並只統計目前抽取器輸出的換行與控制標記。這是翻譯前的資料契約，
不是文字 renderer、codepage 或 glyph identity 的證明。

## 方法與安全界線

- 輸入是 `research/tales-of-the-world-narikiri-dungeon-3-decoded.jsonl`，由
  `tools/extract_strings.py` 重新產生；該檔案保留在本機 ignored 路徑。
- `tools/ledger_metadata.py` 逐筆要求 `sjis:0xNNNNNN`、`locale=ja`、decoder
  version、區域與 raw length，並以 UTF-8 text 雜湊對齊 `core/ledger/ledger_codec.rb`。
- 提交的 `translations/ledger.jsonl` 只保留 `string_id`、`source_hash`、
  `source_locale`、`decoder_version`、區域／控制標記名稱、空白 zh-TW／zh-Hans
  target 與 `untranslated` 狀態；不含 `source` 欄位與原文 text。
- `--verify` 會用本機 source table 重新計算每筆 hash，任何 decoder drift、ID
  重複、順序／內容差異都失敗。它不會把 ledger 當成已解出的碼頁。
- `%0t`、`%0g`、`%h`、`%k`、`%l`、`%d` 等 `%` 形式與 `{HH}` 只被記為 byte-level
  token 候選；其參數語義、換行寬度與 renderer 行為仍是 unknown。

## 已確認／暫定／負結果

### Confirmed

- source-separated ledger builder 與 hash drift check 為 deterministic；輸出沒有
  原文欄位。
- 目前 strict extractor 的 record ID／region／raw length 可被逐筆重新驗證。

### Provisional

- ledger 的 `source_hash` 代表 `tow-nd3-sjis-nul-v1` 的 strict Shift-JIS/NUL
  候選輸出，不代表遊戲 runtime 已採用標準 Shift-JIS。
- 控制標記名稱只反映 source table 的顯式 `{HH}`／`%` token，不能據此開始改寫
  文字或增加容量。

### Negative / unknown

- M1.8 clean trace-first 仍為 `source_read_count=0`，state 7 真正文字 consumer
  尚未取得；因此本帳本不可視為 runtime-valid translation source。
- codepage→glyph、字寬、指標更新、壓縮／回插邊界尚未證明；所有 target 維持空白。

## 重跑

```sh
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 \
  games/tales-of-the-world-narikiri-dungeon-3/tools/ledger_metadata.py \
  games/tales-of-the-world-narikiri-dungeon-3/research/tales-of-the-world-narikiri-dungeon-3-decoded.jsonl \
  --ledger-out games/tales-of-the-world-narikiri-dungeon-3/translations/ledger.jsonl \
  --metadata-out /private/tmp/tow-nd3-ledger-summary.json

PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 \
  games/tales-of-the-world-narikiri-dungeon-3/tools/ledger_metadata.py \
  games/tales-of-the-world-narikiri-dungeon-3/research/tales-of-the-world-narikiri-dungeon-3-decoded.jsonl \
  --ledger-out games/tales-of-the-world-narikiri-dungeon-3/translations/ledger.jsonl \
  --metadata-out /private/tmp/tow-nd3-ledger-verify.json --verify
```

以上命令的 source table、JSON summary 與任何 raw dump 都不應加入 Git。
