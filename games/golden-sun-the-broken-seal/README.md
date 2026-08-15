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

目前已完成 2,802／11,115 條（25.2%）：

- `translations/system-messages.draft.jsonl`：id 0–30，存檔／資料處理 UI，31 條。
- `translations/battle-shop-config-and-defaults.draft.jsonl`：id 31–116，戰鬥指令、商店／設定關鍵字，68 條（原 75 條，因角色預設名姓名緩衝區截斷 bug 移除 id 102–108 七條，見下方「角色預設名 bug」）。
- `translations/items-weapons-and-armor.draft.jsonl`：id 117–1118，武器／防具／道具資料庫，737 條。
- `translations/djinn-names.draft.jsonl`：id 1119–1350，精靈名稱與四系召喚，202 條。
- `translations/shared-corpus-reuse.draft.jsonl`：id 1350 以後散布全 ROM 範圍與第二部逐字相同的系統／戰鬥／道具／劇情文字，1,764 條。

全部通過 `schemas/localization-record.schema.json` 驗證，且逐一與《失落的時代》既有語料庫按「去除控制碼後原文完全相同」比對——能重用的直接沿用既有審訂譯文，找不到的才新譯（見各檔 `review_notes`）。全 ROM 範圍另有 744 條原文即為單一半形「?」、無任何控制碼的除錯／未用插槽佔位字串，比照既有 `?`／`???` 慣例原樣保留、不列入翻譯批次。

`tools/build_translation_batch.py` 的重用比對已加強為**同時核對控制碼結構**，不只比對顯示文字：即使兩作原文逐字相同，其控制碼（換行位置、`{HH}` 插值標記、終止碼）仍可能不同（例如同一句話在第一部多一個換行，或插入的角色索引參數不同），直接照搬 GS2 譯文會導致建置失敗（`translated control-code mismatch`），甚至（若手動繞過檢查）在遊戲內顯示錯誤的插值內容。工具現在會針對每個候選逐一核對控制碼序列是否與本作原始資料完全吻合，不吻合的一律歸類為「需要新譯」，不強行沿用。

### 人名／地名一致性

第一、二部劇情連貫、共用世界觀，玩家會接續遊玩，音譯人名地名不可兩作不同。已將第二部 `translations/glossary.zh-TW.tsv`（222 條）逐條比對第一部全量解碼文字，116 條確認同見（含兩作共通的七名可命名角色：羅賓、傑拉德、伊萬、米雅莉、加西亞、潔絲敏、西芭），寫入第一部自己的 `translations/glossary.zh-TW.tsv`；4 條字串比對誤判（如「シン」只出現在「アサッシンソード」等複合外來語中）已排除。詳見 `research/jp-codepage-derivation.md`「人名／地名跨作一致性」一節與 `tools/build_shared_glossary.py`。之後的翻譯批次應先查此檔，遇到已收錄的專有名詞一律沿用，不另行新譯。

（2026-08-15 更新：依社群主流命名核對結果，メアリィ／席芭 兩名分別改為「米雅莉」「西芭」，第一部與第二部語料庫已同步修正，見下方「建置成果」。）

### 建置成果（2026-08-15）

第一部自己的擴充／指標逆向已完成，`tools/expand_rom.rb`＋`tools/build_zh_tw_trial.rb` 已可從乾淨日版 ROM 產出可燒錄 BPS 補丁：

- ROM 擴充：8 MiB 原始 ROM 補零擴充至 10,485,760 bytes（`tools/expand_rom.rb --size 10485760`），插入點固定於 `0x800000`（原始 ROM 結尾）。
- 指標常數（與第二部不同，第一部每個角色各有兩處字面量參照，需全部同步修補，否則另一條程式路徑仍讀舊表）：
  - 字型指標字面量：`0x157e4`、`0x179a0`
  - Huffman 指標字面量：`0x1556c`、`0x19d04`
  - 文字指標字面量：`0x155cc`（僅一處）
- 字型來源：`../golden-sun-the-lost-age/research/vendor/fusion-pixel-font-10px-monospaced-bdf-v2026.08.11/fusion-pixel-10px-monospaced-zh_hant.bdf`（與第二部同一版本，SIL OFL 1.1 授權，已 SHA256 核對）。
- 建置指令：

```sh
ruby tools/expand_rom.rb \
  --rom roms/base/Ougon_no_Taiyou_Hirakareshi_Fuuin_JP_AGSJ01.gba \
  --size 10485760 \
  --output roms/build/Ougon_no_Taiyou_Hirakareshi_Fuuin_JP_AGSJ01.expanded.gba

ruby tools/build_zh_tw_trial.rb \
  --rom roms/build/Ougon_no_Taiyou_Hirakareshi_Fuuin_JP_AGSJ01.expanded.gba \
  --text-ids research/jp-text-ids.tsv \
  --codepage codepages/ja-extended.tsv \
  --translations translations/system-messages.draft.jsonl \
  --translations translations/battle-shop-config-and-defaults.draft.jsonl \
  --translations translations/items-weapons-and-armor.draft.jsonl \
  --translations translations/djinn-names.draft.jsonl \
  --bdf ../golden-sun-the-lost-age/research/vendor/fusion-pixel-font-10px-monospaced-bdf-v2026.08.11/fusion-pixel-10px-monospaced-zh_hant.bdf \
  --output roms/build/golden-sun-tbs-zh-tw-trial.gba
```

驗證結果（最新一次建置，2,802 條譯文，涵蓋 id 0–11114 全範圍散布區段）：

| 項目 | 結果 |
| --- | --- |
| 目標 ROM CRC32 | `9d1efd45` |
| BPS 補丁 CRC32（`bps_create.rb` 輸出的 patch CRC32，非整檔 CRC32） | `8936be8e` |
| BPS 補丁大小 | 2,097,218 bytes |
| 重新抽取比對 | 全部 11,115 條可解碼，逐位元組與建置腳本輸出一致 |
| `verify_text_delta.rb` | 變動 ID 集合與五份翻譯批次宣告 ID 完全相同（2,802 條） |
| BPS 往返校驗 | 對乾淨 ROM 套用補丁後與直接建置產物逐位元組 `IDENTICAL` |
| mGBA／點陣直讀 QA | 見下方「角色預設名 bug」與「實機驗證範圍」 |

（注意：`ruby ../../core/golden-sun/extract-huffman-text-ids.rb` 的 `--huffman-pointer-table`／`--string-pointer-table` 參數吃的是 ROM **檔案內偏移量**，不是建置腳本印出的 `0x08xxxxxx` GBA 位址——後者要先減去 `0x08000000` 基底才能餵給抽取工具，否則會報 `32-bit read outside ROM`。）

### 角色預設名 bug：名字緩衝區單位元組截斷（已修復）

首次建置（1,045 條，含 id 102–108 七個可命名角色的預設名翻譯，如「羅賓」）在 mGBA 中開新遊戲，喚醒對話「おきるのよ ロビン。」的名字位置顯示成亂碼「34」，命名輸入畫面的預覽框同樣顯示「34」而非預期的中文名字。

原因：遊戲以控制碼 `{11}{01}` 從存檔用的「姓名緩衝區」插入主角名字，該緩衝區**每字元只佔 1 byte**（原版遊戲只會存放假名／ASCII，且命名輸入鍵盤本身也只能輸入假名）。新遊戲初始化時，引擎把預設名字串（id 102，`PC01`）複製進此緩衝區；若該字串被翻譯成中文，其擴充字形 ID（如「羅」=`0x233`、「賓」=`0x234`）會被截斷成低位元組（`0x33`＝ASCII `'3'`、`0x34`＝ASCII `'4'`），因此顯示「34」——與觀察到的亂碼完全吻合。這個截斷發生在遊戲自己的姓名複製路徑，不是指標表或 Huffman 解碼的問題（`verify_text_delta.rb` 對這批字串的一般性解碼驗證本來就是通過的）。

修復：`translations/battle-shop-config-and-defaults.draft.jsonl` 移除 id 102–108（七個角色預設名），保留原始假名不譯——姓名緩衝區的單位元組限制與命名輸入鍵盤只能輸入假名，兩者共同決定了整個姓名系統只能自洽於假名，不宜翻譯。移除後批次總數由 1,045 降為 1,038，已重新建置並通過上表全部驗證；mGBA 複測確認命名畫面與喚醒對話均正確顯示「ロビン」。

**同類風險見於第二部**：《失落的時代》語料庫（`../golden-sun-the-lost-age/translations/`）同樣翻譯了角色預設名（id 131–137 一類），若其姓名緩衝區為相同單位元組設計，其試建置 ROM 極可能有同樣的截斷 bug；第二部尚未有實機 QA 通過命名畫面的紀錄。已在第二部 `ROADMAP.md` 記錄此風險，作為下次建置前的必查項。

### 實機驗證範圍

- mGBA 無頭執行（libmgba C API）確認：Nintendo／Camelot 商標畫面、標題畫面、命名輸入假名鍵盤（含上述 bug 修復後的「ロビン」正確顯示）、開場喚醒對話正常渲染。
- 因開場為强制過場，尚未在模擬器內實際走到會顯示本批翻譯（系統訊息／戰鬥指令／道具／精靈名稱）的畫面；改以直接讀取建置後 ROM 在指標重定向後的真實位置（`0x800000` 起的擴充字型點陣資料）逐字元渲染多組已翻譯字串（如「設定項目」「文字速度」「記錄完成。」），確認點陣資料與指標表皆正確，視覺上清晰可辨、無亂碼或缺字。
- 尚未驗證：實際遊玩路徑觸發戰鬥／商店／存檔選單等會顯示本批翻譯內容的畫面。
