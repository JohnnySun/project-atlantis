# A9PJ M47 fixed static prompt ledger／target glyph policy（2026-08-17）

本切片完成一條不依賴 runtime debugger 的小閉環：M45 已固定的單一選擇提示 source
row，經 M47 的 fail-closed static ledger mode、外部本機字型輸入、七個空白 font
record 槽、pointer relocation、re-extract、BPS create/apply。它只開放這一列的 bounded
ledger／target POC；不增加 M29+ provisional candidate、不能代表 general codepage、
non-UI scene、控制碼 schema 或 patched mGBA runtime QA。

## ROM guard 與共用工具

clean A9PJ local ROM 使用共用身分工具重跑：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 scripts/gba-rom-identity.py \
  /private/tmp/project-atlantis-a9pj.gba \
  --expect-size 8388608 --expect-game-code A9PJ \
  --expect-crc32 9c534023 \
  --expect-sha256 b41c293fc0ed6111b7a37d960d9cd0c685e5d521a4739e0e2eaa7ff6186cfdd3 \
  --expect-title 'TOW SUMMLINE' --expect-maker-code AF \
  --allow-invalid-header \
  --output /private/tmp/tow-m47-target-poc/a9pj-identity.json
```

exit `0`、report `status=pass`。`--allow-invalid-header` 是明示的既知條件：這個 dump 的
header complement 仍為 mismatch；size、code、maker、CRC32 與 SHA-256 都按 expected
通過。ROM 與 report 不進 Git。

## M24 direct caller 的精確邊界

既有 M24 rows `0x2006D6`／`0x20070A` 的 direct consumers 是
`0x08066B60`／`0x08066B76`，共同進入 `0x08066B38`。上游 `0x080667E0` 先建立
display／resource object、寫 display register，再由 `0x08066900` 呼叫資源初始化；
`0x08066B38` 以 object field `r4+0x44`、selector `r1=1/2` 選兩個 ROM literal
`0x082006D6`／`0x0820070A`，並以 `r0=r4+0x28`、`r1=0x21`、`r3=0x0F` 呼叫
`0x080063E0`。這證明它們是另一個 display／object data consumer，但沒有 live scene
state、reader hit 或可核對的地圖／事件／角色／戰鬥語意；private raster 只足以將它們
保留為 `system-ui-static-candidate`，不提升為 non-UI row，也不與 M1.7 font-record
caller 合併。

## M47 source gate

`m21_source_decoder.py --known-static-ledger-only` 只重用 M45 的第一條 fixed prompt：

| 欄位 | receipt |
| --- | --- |
| `string_id` | `7315f99d621763293ecba441` |
| source file offset | `0x1FAA24` |
| static caller | `0x080509CC` |
| source stream SHA-256 | `e9cdfcfc0abc566036981065a0d4e5a62493acf84d785e9d4cfdba8c94acde29` |
| source hash | `b4febd649a6d802e024ecd790f6a3a22d63021e5f8e4ef4b8cd6270980ec69a4` |
| raster SHA-256 | `057f9cb06669b5e0a9c8cb61978629495bace2463bd2120a5d719b854792cc23` |
| terminator | `0x0000` |
| unresolved／control candidate | `0`／`0` |
| decoder | `m47-known-static-ledger-decoder-20260817.v1` |
| ledger gate | `1 fixed row; runtime=false; general-codepage=false` |

此 mode 不是 broad scan，也不改寫 M45 其餘兩列的 `eligible_for_ledger=false`；source
text 只在 `/private/tmp/tow-m47-target-poc/static-ledger-source.jsonl`，提交檔只留
`source_hash`。

## target glyph／font policy

目標側固定為 `請選擇要攻擊的單位。`，共 10 個 code unit；既有已交叉 glyph
`選=0x03A8`、`攻=0x04F4`、`。=0x0003` 重用，其餘七字使用 clean ROM 中原本全零的
24-byte record slot：

| target glyph | code unit | record file offset | patched record SHA-256 |
| --- | ---: | ---: | --- |
| 請 | `0x0F95` | `0xA13F8` | `5c00f1092574d84b4d720ce0cddfc45dfd06f62215a8644f178e18d649a2e366` |
| 擇 | `0x0FAA` | `0xA15F0` | `915dc8b6d15bc50ecc6de0347dfb0292a041afd4cc3fd43f2efdf663298b239a` |
| 要 | `0x1051` | `0xA2598` | `0f2da518c8ffed7b9b888859321db1b8802d6d12f0cfb54842cdad22616fb292` |
| 擊 | `0x10FD` | `0xA35B8` | `6631e749d5e5edfba9e7b527cff6cc354c2b8c4351b59c421d31116663ea371b` |
| 的 | `0x110F` | `0xA3768` | `58fc9f4b68e1286b85df8595a7f9f67849131b2ac839e2a68928630eac01fb13` |
| 單 | `0x11BF` | `0xA47E8` | `f6b1db78b6fd17ecde9d58cbc63ecb9f9020328e92067171ded02429d439d61e` |
| 位 | `0x11E5` | `0xA4B78` | `dd8b52526a3189aeecdf5b2cb75244b505b2b968e05cd8d9716ee2c182774e9c` |

固定政策為：

- 外部字型由命令列 `--font` 明示提供；本次 local input 是 NotoSansCJKtc-Regular，
  SHA-256 `dce08bd4fd91aa8aa76ed8fea4b694c2dfb8550f67871e326843212ddbeb88b4`，字型檔
  不提交。
- Pillow／FreeType 10px、threshold `128`、16×12、1bpp、MSB-first；任何 glyph
  超出 16×12 直接 fail closed，不裁切。生成的七個 24-byte record 只寫入原本全零
  slot；工具會再次檢查 clean slot、record hash 與 target record hash。
- 這是 `m47-noto-cjk-tc-16x12-threshold128-v1` 的 bounded target policy，不是
  general CJK encoder；尚未證明完整字庫容量、所有 source code unit 不碰撞或 patched
  runtime 的實際可讀性。

可重跑命令（ROM、font、target image、receipt 皆留 private）：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 \
  games/tales-of-the-world-summoners-lineage/tools/m33_target_reinsertion_poc.py \
  /private/tmp/project-atlantis-a9pj.gba --profile m47 \
  --target-text '請選擇要攻擊的單位。' \
  --font /Users/bmy001/Library/Fonts/NotoSansCJKtc-Regular.otf \
  --output /private/tmp/tow-m47-target-poc/target.gba \
  --receipt /private/tmp/tow-m47-target-poc/receipt.json
```

tool receipt 通過：pointer `0x081FAA24→0x08800000`、target stream `22` bytes、
terminator `true`、target record checks `7/7`、原七個 slot 全 blank、re-extract
unresolved `0`，source stream unchanged `true`。target image SHA-256
`56638962b8da27e51397b0dafbe6c9623d72affea269da570968a7b09f04d5fd`、CRC32
`393465f9`。BPS 為 `226` bytes、SHA-256
`b02aae9845b2730f79a75a46eead0e227e6ca040d410d32f2a86fb47479c2eba`；apply 後與 target
image byte-identical。這些產物均未提交。

## ledger 邊界與未完成項

`restore_translations.rb`／`strip_translations.rb` 已對這一列完成 local source hash
round-trip；新增的 `translations/m47-static-attack-prompt.jsonl` 沒有 `source` key。
target phrase、寬度與 `control_codes=[]` 只代表 bounded static prompt，狀態仍是
`ai_draft`。M47 沒有把 static row 說成 runtime QA，也沒有宣稱 `zh-Hans` 翻譯或
general codepage 已完成；後續仍需確認 target font license／畫面可讀性、patched mGBA
實機、adjacent source re-extract、更多 scene rows、控制碼／版面與完整翻譯覆蓋率。
