# 《世界傳說：召喚者的血統》漢化工作區

本目錄只處理日版 GBA《テイルズ オブ ザ ワールド ～サモナーズ リネージ～》
（game code `A9PJ`），目標是臺灣繁體 `zh-TW`。ROM、patch、抽出的原文、工作記錄、
解壓資源與渲染圖片只存在於研究者本機；可提交的翻譯記錄必須遵守
[翻譯帳本方案](../../docs/TRANSLATION-LEDGER.md)，不把 `source.text` 放進 Git。

## 當前狀態

目前完成的是「ROM 身分＋唯讀結構偵察」以及有界 M1／M1.5／M1.6 執行期切片；尚未
開始有限量翻譯，也沒有可回插的文字 patch。M1.6 已在不重做 startup baseline 的
前提下，以 BG1 假名鍵盤簽名安全導航，證明 EWRAM 姓名 buffer 的第一、第二個 code
unit 變動，並以 writer／reader watchpoint 追到 font-record renderer caller；glyph
identity 仍是 provisional，沒有建立 source table／work ledger。詳見
[`research/m16-name-entry-code-unit-20260816.md`](research/m16-name-entry-code-unit-20260816.md)。
M1.5 的圖層與 VRAM negative receipt 仍見
[`research/m15-name-entry-runtime-20260816.md`](research/m15-name-entry-runtime-20260816.md)。
下一個安全技術關卡是把 font-record／runtime tile 的關係、控制碼與劇情／地圖／事件、
角色／戰鬥資料分離，再確認可逆回插規則。

- ROM 身分、大小與雜湊已記錄；標頭補數校驗不一致，這個異常必須保留在基準資料中。
- 全 ROM 未找到常見日文 UI 詞的 literal Shift-JIS 命中，不能把一般 Shift-JIS 當成
  已確認碼頁。
- `0x1f0000`–`0x2c0000` 是高密度 16-bit little-endian／NUL 結尾資料的候選區；
  目前只能說「像文字或表格資料」，尚未把每個指標標成文字。
- `0x4dfde4`（1,333 entries）與 `0x1acf34`（520 entries）兩張指標表的目標全部
  通過 GBA LZ77 解碼，較像圖像／字型等資源，不能拿來當劇本池。
- 外部 v0.20 IPS patch 可作工程參考；其新增資料含 LZ77 資源、字型樣資料與 16-bit
  自訂碼元，但英文譯文不是本專案的日文原文依據。
- M1 的有界擷取 receipt 見 [`research/runtime-text-capture-20260816.md`](research/runtime-text-capture-20260816.md)；
  source table 的本機 row contract 與證據門檻見 [`research/source-table-spec-20260816.md`](research/source-table-spec-20260816.md)。
- 共用 `core/gba` baseline 已確認實際 BG1／BG2／BG3 tilemap 與 startup／演出圖層可
  重建；這是 graphics path 證據，不是事件／選單文字或 codepage 證據，詳見
  [`research/runtime-baseline-core-20260816.md`](research/runtime-baseline-core-20260816.md)。
- M1.5 的互動畫面、glyph addressing、renderer 判定與兩段 bounded negative watchpoint
  receipt 見 [`research/m15-name-entry-runtime-20260816.md`](research/m15-name-entry-runtime-20260816.md)。
- M1.6 的 BG1 八格 metadata／hash、EWRAM/IWRAM diff、`0x02004014` writer／reader
  receipt 與 `0x08089E00 + code_unit * 0x18` font-record arithmetic 見
  [`research/m16-name-entry-code-unit-20260816.md`](research/m16-name-entry-code-unit-20260816.md)。
- M1.6 只確認 code-unit consumer／caller；selected BG1 glyph 的 clean-ROM aligned
  exact match 為零，confirmed glyph identity 為零，故仍不產生 source rows 或翻譯。

## ROM 基準

完整欄位見 [`game.yml`](game.yml)。本次本機唯讀驗證得到：

| 欄位 | 值 |
| --- | --- |
| size | `8,388,608` bytes |
| title / game code / maker | `TOW SUMMLINE` / `A9PJ` / `AF` |
| CRC32 | `9c534023` |
| MD5 | `7bbd6798acfbe798d1e458938afc7a1a` |
| SHA-1 | `c7bda17313fdef597ccec98502e71c7e61281c9b` |
| SHA-256 | `b41c293fc0ed6111b7a37d960d9cd0c685e5d521a4739e0e2eaa7ff6186cfdd3` |
| header checksum / calculated | `0x32` / `0x64`（不一致） |

這表示目前手上的 dump 可以用 `A9PJ` 與雜湊辨識，但不能宣稱是標頭校驗完全乾淨的
pristine dump；後續所有抽取與測試都必須固定這組基準。

## 研究結論與限制

### 已確認

- 對齊 little-endian ROM 指標掃描找到大量指向資料區的引用；專用探針只輸出幾何與
  統計，不輸出原文。
- `probe_resource_pointer_table.py` 逐項解碼兩張大型表：`0x4dfde4` 的 1,333 個
  目標與 `0x1acf34` 的 520 個目標皆是有效 GBA LZ77，沒有標準 Shift-JIS sentinel。
- v0.20 patch 的本機套用結果從 8 MiB 增長到 `8,730,574` bytes；patch 差異中有
  8,251 段、378,567 個變更 bytes，並把 1,616 個原 ROM 指標改接到新增區。這是
  patch 工程證據，不等於 1,616 條劇本。
- 新增區 `0x800000` 起先出現可連續驗證的 LZ77 block；其後出現字型樣資料與 16-bit
  NUL 結尾資料。新增資料的確切碼頁與控制碼仍待 runtime／字形對照確認。

### 尚未確認

- 角色、地圖、事件、戰鬥資料的 record schema 與每個文字欄位的語意。
- 日文 codepage／glyph identity。16-bit code unit 的位址形式已高信心，字元身分仍
  未知；不會用英文 patch 反推日文並直接寫入翻譯。
- 換行、變數、姓名／道具插值、結束碼與其他控制碼。
- ROM → working source table → ledger → 目標 ROM 的完整可逆回插路徑。
- 已有 name-entry 畫面自己的 mGBA／VRAM 圖層證據；但 glyph byte match 仍不是
  codepage／source row 證據，靜態候選與 renderer 圖層不能互相冒充文字 consumer。

## 外部工程參考

- [Bandai Namco 官方產品頁](https://www.bandainamcoent.co.jp/cs/list/summonerslinage/prod/index.html)：
  日文正式標題、Aseria 設定與遊戲類型。
- [v0.20 patch 專案頁](https://www.blade2187.com/projects/summoners-lineage/) 與
  [v0.20 變更說明](https://www.blade2187.com/2025/02/10/summoners-lineage-v0-20/)：
  只保留工程範圍、buffer 限制與版本狀態，不把英文內容當翻譯來源。
- [GameFAQs dialogue translation](https://gamefaqs.gamespot.com/gba/916705-tales-of-the-world-summoners-lineage/faqs/25869)：
  只可作日文語意的外部交叉參考；其作者明示是 approximate translation，不能取代
  日版原文。

zh-Wikipedia 的索引使用過「世界傳奇 召喚士的系譜」這個異名；目前未找到能在
Bahamut 交叉確認的本作條目，因此 `zh-TW` 標題仍是工作名。專有名詞表會等到
日文抽取可讀且完成多來源核對後才建立，不先自行造音譯。

## 帳本與本機流程

```text
research/summoners-lineage-decoded.jsonl  # 本機重建，含 source，已被 .gitignore 排除
work/*.jsonl                              # 本機校對工作記錄，已被 .gitignore 排除
translations/*.jsonl                      # 只提交 strip 後、不含 source 的帳本
```

預定流程：

```sh
/usr/bin/python3 games/tales-of-the-world-summoners-lineage/tools/<decoder>.py \
  <clean-A9PJ.gba> --output games/tales-of-the-world-summoners-lineage/research/summoners-lineage-decoded.jsonl
ruby core/ledger/restore_translations.rb \
  games/tales-of-the-world-summoners-lineage/translations/<batch>.jsonl \
  games/tales-of-the-world-summoners-lineage/research/summoners-lineage-decoded.jsonl \
  games/tales-of-the-world-summoners-lineage/work/<batch>.jsonl
ruby core/ledger/strip_translations.rb \
  games/tales-of-the-world-summoners-lineage/work/<batch>.jsonl \
  games/tales-of-the-world-summoners-lineage/translations/<batch>.jsonl
```

在 codepage、控制碼與 `string_id` 穩定前，不建立翻譯 batch；目前沒有可提交的
`translations/*.jsonl`。

## 工具

工具的輸入 ROM 路徑可以指向本機合法 dump；輸出是結構統計，不會把原文寫入 repo。
使用方式與重現指令見 [`tools/README.md`](tools/README.md)，研究數字與判定界線見
[`research/initial-recon-20260816.md`](research/initial-recon-20260816.md) 和
[`research/patch-engineering-20260816.md`](research/patch-engineering-20260816.md)。
