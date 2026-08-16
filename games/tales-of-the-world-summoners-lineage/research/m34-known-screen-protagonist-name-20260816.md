# A9PJ M34 主角姓名欄位 known-screen cross（2026-08-16）

M34 沿用 M19 的 clean name-entry capture 與 M32 的固定 BG0 raster／tilemap 方法，補做
一個有限的非 Latin glyph slice。它不是新的候選掃描器，也不是 live reader breakpoint：
只驗證一個已知 source pointer、四個 16-bit code unit、四個 24-byte font record、四個
screen mask 與八個 BG0 tile hash。ROM、VRAM、圖片與 source-bearing local table 均留在
`/private/tmp`，本文件只保存 offset、code unit、hash、座標與判定。

## 重現與 gate

工具是既有的 `tools/m29_ui_row_cross_probe.py`，M34 只是其中一個固定 cohort：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 \
  games/tales-of-the-world-summoners-lineage/tools/m29_ui_row_cross_probe.py \
  /private/tmp/tow-a9pj-m24-direct/direct-decoded.jsonl \
  /private/tmp/tow-a9pj-m19-gate-seq-1/summary.json \
  --rom /private/tmp/project-atlantis-a9pj.gba \
  --bg0-image /private/tmp/tow-a9pj-m19-gate-seq-1/bg0-gate.png \
  --bg0-vram /private/tmp/tow-a9pj-m19-gate-seq-1/dump/vram.bin \
  --m17-summary /private/tmp/tow-a9pj-m17-runtime-final/summary.json \
  --protagonist-name-cross \
  --output /private/tmp/tow-a9pj-m34-known-screen/summary.json
```

M34 receipt 的核心結果：

| gate | result |
| --- | --- |
| A9PJ ROM SHA-256 | `b41c293fc0ed6111b7a37d960d9cd0c685e5d521a4739e0e2eaa7ff6186cfdd3`，match |
| keyboard／screen gate | BG1 `8/8`，M19 BG0 image SHA-256 match |
| static source pointer | literal file `0x003E34`，load PC `0x08003E24`，value `0x08087384`，match |
| terminated source span | file `0x087384`，10 bytes，4 code units + `0x0000`，SHA-256 `a996824161672f240ae4ddf9578ffce192cc5464efea28949f08dead2d0f23e9` |
| font-record → screen mask | `4/4` |
| BG0 tilemap entry／tile hash | `8/8` |
| reader breakpoint／raw byte copy | `false`／`false` |
| general codepage／control schema | `false`／`false` |

`0x08003E10` 的 Thumb initializer 在 `0x08003E24` 取該 literal，並將 destination
與 `r2=7` 傳給 `0x0806C2E0`；本文件不假設該參數是 byte 或 code-unit count。source
span 另在 `0x28BF74` 出現相同 hash，但該位置沒有被選作 source provenance；M34 只採用
有 literal pointer 的 `0x087384`。

## code unit／raster／tilemap 三方交叉

font record 仍由 `0x08089E00 + code_unit * 0x18` 定位；每一列只保存 hash 與已知畫面
mask，不保存 24-byte rows 或 tile bytes。

| code unit | known-screen identity | record SHA-256 | screen box | mask SHA-256 | BG0 top/bottom tile entry |
| ---: | --- | --- | --- | --- | --- |
| `0x00C8` | `フ` | `2bbd328bba90164ca0b3b10eff1d260f181454f3b305315703931dcfafcfda14` | `(65,34)-(74,43)` | `ae462e7b71635156eaf20de4c538043a8a1af4d213a882da316b0fd3b44e860c` | `0x0101` / `0x0113` |
| `0x00F6` | `レ` | `11ed35e98e5a20b31a870c1f02c4277aa2c54243c3a3d93636483c1edf8e4b93` | `(78,33)-(86,43)` | `a6228b8b625dad1d6c55e0b569c5c0a5be759b9f23c0e0dd8820ca4ecb9720d4` | `0x0102` / `0x0114` |
| `0x0063` | `イ` | `4e2a7536070a7a01c9b608753351a68183591899973578678e7ae2b6026f705c` | `(88,32)-(97,43)` | `0b8ca2a33b11b1e28fac69641f5a8ae228ceab5d958d5edc94a74c00da87b774` | `0x0104` / `0x0116` |
| `0x00FE` | `ン` | `b125b55c7f58c53b3deedc785a79703855a7502e0610e6bac5435014a00877b9` | `(101,34)-(110,43)` | `fd4fee0e0b579fa395ff61687607ac0f3431380d18904a873712b6ef3732e878` | `0x0105` / `0x0117` |

每個 box 的 crop mask 都與同一 code unit 的 MSB-first 16×12 record mask 相等；BG0
screenbase 的 tilemap cell 又各自指向表列的兩個 tile entry，故這次不是孤立外形或
OCR 猜測。`0x00FE` 雖然可在 keyboard table 找到 row-1 entry，但其 selection slot
本身不被當成 general Katakana mapping；身分判定依 known-screen name context、record
raster 與 tilemap 三方，而不是把 keyboard tail slot 自動命名。

## scene／ledger 邊界

主角姓名欄位的日文身分由畫面與日文官方資料交叉：Bandai Namco 官方角色頁列出
`フレイン・K・レスター` 及其 `Fulein.K.Lester` image label；Game Watch 發售資料
與 Bandai Namco 發布資料也列出同一主角與姓氏。[官方角色頁](https://www.bandainamcoent.co.jp/cs/list/summonerslinage/chr/index.html)、
[Game Watch 發表資料](https://game.watch.impress.co.jp/docs/20030109/samo.htm)、
[Bandai Namco 發布 PDF](https://www.bandainamcoent.co.jp/corporate/press/namco/48/48-046.pdf)
與[日文社群條目](https://w.atwiki.jp/gcmatome/pages/2979.html)是獨立 provenance。

目前沒有找到可在臺灣 Wikipedia 或巴哈姆特直接核對本作角色的頁面；中文舊攻略索引
可作遊戲異名／人名線索，但沒有形成足夠的多來源主流譯名。因此 M34 只把四個日文
glyph identity 提升為 known-screen confirmed，target 姓名仍 terminology-pending；
不在本輪新增翻譯列，也不把官方 Latin label 當作 zh-TW 定案。

這一列可進入 **private** source／ledger gate：source span、terminator、scene role、
record identity、screen cross 與 checksum 都有證據；提交的 ledger 若建立，仍只能含
`source_hash`，不得包含 source text。M34 沒有證明 general Japanese/CJK mapping、
variable／name／item control、live reader 或 CPU/DMA byte-identical copy。

## M34 private ledger／回插 POC

以 M34 source span 建立的 private row 使用 stable ID
`f4bc65e10318a0204bebc5b0`。`restore_translations.rb` 需要 ledger 先帶有
`source_hash`；缺少該欄位時會 fail closed，補入由 source table 計算的
`8c24214195799be96f68bbd812d4ae8de1a086856c20846cf18c629f1f4283e4` 後，
restore→strip receipt 為：

```text
source_hash == ledger_source_hash == stripped_source_hash
stable_id_preserved = true
targets = zh-Hans + zh-TW
stripped_contains_source_key_or_text = false
```

private `m33_target_reinsertion_poc.py --profile m34` 再將 bounded official Latin target
`Fulein` 編成 6 個 code unit + `0x0000`，把 stream append 到 `0x800000`，並只改寫
file `0x003E34` 的 `0x08087384 → 0x08800000` pointer：

| receipt | result |
| --- | --- |
| target image | 8,388,622 bytes，SHA-256 `c0b28bfe039ba828783e9a3ea36398754be31bc080fc7f40861bce1f48d82bcb` |
| relocated stream | 14 bytes，SHA-256 `4d38b4cde1e4990ef5573f2d2e56869cd30e29c068808d3eb00283ff7094fb34` |
| encoded target | 12 bytes，SHA-256 `64478cd575a409ef1c86b8c78d2780631f428596c61034c31b04b1c35b48c5f1` |
| BPS | 51 bytes，SHA-256 `7aed24815b443895f98815431c59cb2d5ad3b22c7d4a142c1b0882fe0214c7b1` |
| BPS apply | target image byte-identical |
| original source span | unchanged；原 8 MiB 內只有 3 bytes（pointer literal）變更 |
| runtime QA | `false` |

這證明第二個 bounded source-hash／target relocation／BPS plumbing path，但 target 仍
`terminology-pending`，沒有建立可發布的 zh-TW 翻譯，也沒有把 M34 static pointer 當成
live runtime reader 或 fixed-slot policy。

## 判定摘要

```text
scene_role_candidate = ui-name-entry-protagonist-name-field
runtime_context_proof = known-screen-static-source-pointer-record-raster-and-tilemap-correlated
glyph_identity_confirmed_by_this_probe = 4
source_pointer_confirmed = true
eligible_for_ledger = true (bounded row only)
general_codepage_confirmed = false
control_schema_confirmed = false
```

下一個最小缺口是取得一個可獨立驗證的 general Japanese／CJK mapping 或控制碼 consumer，
並把 fixed-width／relocation policy 接到 clean re-extract；一般劇情、地圖／事件、角色與
戰鬥 rows 仍不得批次進 ledger，patched mGBA runtime QA 也尚未成立。
