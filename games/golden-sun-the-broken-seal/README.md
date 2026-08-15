# 《黄金太阳 开启的封印》汉化修订工作区

本目录用于研究和修订 2024 年 12 月 8 日发布的《黄金太阳 开启的封印》新汉化公开测试版，并生成可复现、可校验的通用 GBA 补丁构建。

## 当前状态

- 日版原 ROM 已通过发布说明要求的 CRC32、MD5 和 SHA-1 校验。
- 官方公开测试版 BPS 已成功应用，BPS 的源、目标和补丁 CRC32 均通过。
- 已抽取并核对日文／中文各 11,115 条文本索引；未发现结构性漏译。
- 已定位新版直接字符串表、自定义中文码页及字体渲染钩子；Unicode 映射与逐句校对仍在进行。

## 目录

- `roms/base/`：日版原 ROM 和原始压缩包，仅限本地使用，不进入 Git。
- `roms/build/`：当前及后续构建产物，仅限本地使用，不进入 Git。
- `upstream/2024-public-beta/`：原始 BPS、汉化说明和附带文档，仅限本地使用。
- `tools/bps_apply.rb`：带源、目标和补丁 CRC32 验证的 BPS1 应用器。
- `research/unfinished-scope.md`：公开测试版已知的未完成范围与边界。
- `research/audit-20260814.md`：字符串完整性与程序改动的首轮二进制审计。
- `ROADMAP.md`：后续逆向、校对、测试和发布步骤。

## 基准校验

| 文件 | 大小 | CRC32 | MD5 | SHA-256 |
| --- | ---: | --- | --- | --- |
| 日版原 ROM | 8,388,608 | `fb96d9de` | `cf33e45e59b0ee3801b5cf18a9e58524` | `088bedae4bad8b67e87ff10035a898d3639f3182d486fe5a5d113bab223e0a26` |
| 2024 公开测试版 ROM | 11,594,160 | `d54a0ae9` | `7e64b85b584995c32bc0b349f31cc79e` | `f566de927b4ccf95e55686553db3089c26b842158d49a2a91472a8b6ba1419bc` |
| 上游 BPS | 981,631 | `de428ef4`（BPS 内置） | `918956dccc019995b108b55629578388` | `666bbfa5210d4ee2835c901f4f362727492f6ac414cda7a75de2f6c18bd06486` |

## 重建公开测试版

```sh
ruby tools/bps_apply.rb \
  roms/base/Ougon_no_Taiyou_Hirakareshi_Fuuin_JP_clean.gba \
  'upstream/2024-public-beta/黄金太阳开启的封印_2024新汉化版(公开测试版)_20241208_汉化补丁.bps' \
  roms/build/golden-sun-cn-public-beta.gba
```

构建后必须再次确认目标 CRC32 为 `d54a0ae9`，否则不得作为有效测试构建使用。

## 测试构建原则

ROM、个人存档、实验构建和本机路径不进入公开仓库。测试前应核对输入与构建产物的哈希，并保留上一份已验证构建；不要修改或删除 `.sav`、`.srm` 等存档。

## 從日版直接漢化（比照《失落的時代》做法）

以上「修訂 2024 公開測試版」與本節「從乾淨日版 ROM 直接漢化」是**兩條獨立路線**，共用同一份日版原 ROM 基準，互不覆蓋。2024 公開測試版僅作語義參考，不得將其譯文直接抄入翻譯 JSONL（比照 `../golden-sun-the-lost-age` 對舊中文版參考樣本的原則：以日文原案為準）。

### 版本確認

- 日版原 ROM：`region: JP`、`game_code: AGSJ01`、`revision: 0`，與 `game.yml` 記錄的 CRC32 `fb96d9de`／MD5 `cf33e45e59b0ee3801b5cf18a9e58524`／SHA-1 `35ef9e4c9f38183ebd6a3e3923a11ce9a4333718`／SHA-256 `088bedae4bad8b67e87ff10035a898d3639f3182d486fe5a5d113bab223e0a26` 逐位元組核對一致（`roms/Original` 本機收藏第 0079 號）。
- 《失落的時代》使用的日版原 ROM 為 `AGFJ01 rev 0`（`roms/Original` 第 0489 號），已同樣核對一致；兩作日版均只有單一修訂版本，無需另尋其他 revision。

### 文字佈局

| 項目 | ROM offset |
| --- | ---: |
| Huffman 上下文指標入口 | `0x03bb68` |
| 字串分塊指標表 | `0x06c040` |
| 訊息數 | `11,115`（與既有審計一致） |
| 擴展字形點陣表 | `0x33b30`（24 bytes／字形，比對第二部字型格式尋得） |

```sh
ruby ../../core/golden-sun/extract-huffman-text-ids.rb \
  --rom roms/base/Ougon_no_Taiyou_Hirakareshi_Fuuin_JP_AGSJ01.gba \
  --output research/jp-text-ids.tsv \
  --count 11115 \
  --huffman-pointer-table 0x03bb68 \
  --string-pointer-table 0x06c040
```

### 日文碼表

基礎假名（0x20–0xff）是引擎內建表，兩作共用，已驗證可直接沿用（`core/golden-sun/japanese_codepage.rb`）。**擴展字形（0x100+）不可比照沿用**——見
`research/jp-codepage-derivation.md`：兩作各自依「本作文字表中首次出現順序」配置擴展字形 ID，結構上兩作 ID 範圍雖大致重疊，語義卻不保證相同（實測第二部碼表套用於第一部時，100% 的字形都「查得到字」，但至少一組字元指派錯誤，解出「後名」這種不存在的日文詞）。

改以**字形點陣比對**取代直接沿用或 OCR：兩作字型渲染格式相同（24 bytes／字形），比對第一部與第二部 ROM 的原始點陣資料，逐一還原第一部自己的擴展碼表，114 個擴展字形**全數比對成功**，且全部語意檢查通過（見 `research/jp-codepage-derivation.md` 的 sentinel 檢查表）：

```sh
python3 tools/derive_codepage_by_raster.py \
  --target-rom roms/base/Ougon_no_Taiyou_Hirakareshi_Fuuin_JP_AGSJ01.gba \
  --target-font-base 0x33b30 --target-count 114 \
  --reference-rom ../golden-sun-the-lost-age/roms/base/Ougon_no_Taiyou_Ushinawareshi_Toki_JP_AGFJ01.gba \
  --reference-codepage ../golden-sun-the-lost-age/codepages/ja-extended.tsv \
  --reference-font-base 0x05bf8c \
  --output codepages/ja-extended.tsv
```

解碼全量文字：

```sh
ruby ../../core/golden-sun/decode-text-ids.rb \
  --text-ids research/jp-text-ids.tsv \
  --codepage codepages/ja-extended.tsv \
  --output research/jp-decoded.jsonl
```

### `zh-TW`／`zh-Hans` 試譯批次

第一部與第二部有大量共用系統文字（存檔、資料處理、隊伍加入、精神力學習等 UI 訊息，兩作原句逐字相同）。`tools/build_translation_batch.py` 以「去除控制碼後的原文是否與第二部語料庫完全相同」為準，沿用第二部已審訂的 `zh-Hans`／`zh-TW` 譯文；找不到完全相同原句的條目留待新譯，不臆測套用相近譯文。

目前已完成 id 0–1350 區間，共 1,045 條（另有 306 條 `?`／`???` 佔位或除錯標籤依《失落的時代》既有慣例原樣保留，不列入翻譯批次）：

- `translations/system-messages.draft.jsonl`：id 0–30，存檔／資料處理 UI，31 條。
- `translations/battle-shop-config-and-defaults.draft.jsonl`：id 31–116，戰鬥指令、商店／設定關鍵字、角色預設名，75 條。
- `translations/items-weapons-and-armor.draft.jsonl`：id 117–1118，武器／防具／道具資料庫，737 條。
- `translations/djinn-names.draft.jsonl`：id 1119–1350，精靈名稱與四系召喚，202 條。

全部通過 `schemas/localization-record.schema.json` 驗證，且逐一與《失落的時代》既有語料庫按「去除控制碼後原文完全相同」比對——能重用的直接沿用既有審訂譯文，找不到的才新譯（見各檔 `review_notes`）。

### 人名／地名一致性

第一、二部劇情連貫、共用世界觀，玩家會接續遊玩，音譯人名地名不可兩作不同。已將第二部 `translations/glossary.zh-TW.tsv`（222 條）逐條比對第一部全量解碼文字，116 條確認同見（含兩作共通的七名可命名角色：羅賓、傑拉德、伊萬、米雅、加西亞、潔絲敏、席芭），寫入第一部自己的 `translations/glossary.zh-TW.tsv`；4 條字串比對誤判（如「シン」只出現在「アサッシンソード」等複合外來語中）已排除。詳見 `research/jp-codepage-derivation.md`「人名／地名跨作一致性」一節與 `tools/build_shared_glossary.py`。之後的翻譯批次應先查此檔，遇到已收錄的專有名詞一律沿用，不另行新譯。

### 尚未完成（下一里程碑）

建置可燒錄 BPS 補丁前，還需要：

- 定位第一部原始日文字型渲染／Huffman／文字指標在程式碼中的參照位址（第二部 `tools/build_zh_tw_trial.rb` 的 `font_pointer_literal`／`huffman_pointer_literal`／`text_pointer_literal` 等常數與其 16 MiB ROM 版面綁死，不能直接套用於 8 MiB 的第一部，需要重新逆向）。
- 定位第一部 ROM 內足夠大的空白擴展區（第二部使用 `0xf80000`，第一部 ROM 只有一半大小，需另尋位置）。
- 擴充翻譯批次覆蓋全部 11,115 條文字，並比照第二部流程執行 `verify_text_delta.rb`、BPS 產生與往返校驗、mGBA 實機 QA。
