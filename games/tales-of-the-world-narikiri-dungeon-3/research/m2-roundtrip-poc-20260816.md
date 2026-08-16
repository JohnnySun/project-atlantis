# M2 等長 record／重抽取／BPS POC（2026-08-16）

## 範圍與安全邊界

本回合只驗證一個 **synthetic、非翻譯** replacement 的工程 round-trip。可重跑工具
是 [`tools/bounded_roundtrip_poc.py`](../tools/bounded_roundtrip_poc.py)；它只接受
五窗 strict extractor 已確認的 exact record start、等於 `raw_length` 的 payload，
並 fail-closed 拒絕 interior NUL、`0xFF`、控制／換行序列變更與 record span 外差異。
clean ROM、patched ROM、BPS、applied ROM 與 JSON summary 全留在 `/private/tmp`；Git
只保留本文件、工具與測試，不含 source text、raw payload、ROM 或 patch。

replacement `A1A2A3A4` 只是 4-byte parser-fixture，用來驗證 selected
`sjis:0x146EE0` 的等長 mechanics，不是日文→zh-TW 譯文，也不進 ledger。這一點很
重要：8,938 筆 ledger 仍全部 `untranslated`。

## Confirmed bounded receipt

| 項目 | 結果 |
| --- | --- |
| clean identity | `TOWNARIKIRI3`／`B3TJ`／16 MiB／CRC32 `1867CCEF` |
| selected record | `sjis:0x146EE0`／`text-pool`／`raw_length=4` |
| source／target strict record count | `8938`／`8938` |
| record start set／target raw length | equal／equal |
| changed bytes | `4`，全在 selected payload |
| control/newline sequence | preserved |
| untouched record bytes／outside span | equal／equal |
| target CRC32 | `775EA2C5`（patched ROM 改變 CRC，屬預期） |
| BPS create | core `bps_create.rb`，38 bytes，patch CRC32 `20BD375F` |
| BPS apply | core `bps_apply.rb`，applied SHA-256 與 patched SHA-256 相同 |
| strict re-extract of applied ROM | `8938` high-quality records；使用 `--skip-identity-check`，因 clean CRC gate 不應接受 patched CRC |

這證明 **confirmed-poc-only**：在不改變 record 長度、NUL 邊界與 control/newline
sequence 時，可以產生一個只改 selected payload 的本機 ROM copy，並以 core BPS
往返重建。它沒有讀出或提交 replacement／source 的原文表示。

## 未證明與下一步

- `0x08015B74`／`0x080021A8` 的 live source consumer、decoder、code-unit→glyph
  identity、RAM→VRAM writer：**unconfirmed**。
- `A1A2A3A4` 不是 zh-TW 字串，不能用來宣稱字型、碼頁、字寬或畫面可讀性。
- selected record 的容量只在「等長 payload」這個 POC 邊界成立；變長、pointer rewrite、
  壓縮 resource、header/checksum policy 與完整 BPS builder：**unconfirmed**。
- M2 builder checkbox 仍未完成；必須先取得真實 text consumer、控制碼／碼頁／glyph
  證據，才可將這個 fail-closed harness 擴充成 translation ledger adapter。

## 重跑命令

```sh
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 \
  games/tales-of-the-world-narikiri-dungeon-3/tools/bounded_roundtrip_poc.py \
  games/tales-of-the-world-narikiri-dungeon-3/roms/base/Tales_of_the_World_Narikiri_Dungeon_3_JP_AGB-B3TJ-JPN.gba \
  --record-offset 0x146EE0 --replacement-hex A1A2A3A4 \
  --patched-rom /private/tmp/tow-nd3-m2-roundtrip-poc.gba \
  --summary /private/tmp/tow-nd3-m2-roundtrip-poc.json

ruby core/patches/bps_create.rb \
  games/tales-of-the-world-narikiri-dungeon-3/roms/base/Tales_of_the_World_Narikiri_Dungeon_3_JP_AGB-B3TJ-JPN.gba \
  /private/tmp/tow-nd3-m2-roundtrip-poc.gba \
  /private/tmp/tow-nd3-m2-roundtrip-poc.bps

ruby core/patches/bps_apply.rb \
  games/tales-of-the-world-narikiri-dungeon-3/roms/base/Tales_of_the_World_Narikiri_Dungeon_3_JP_AGB-B3TJ-JPN.gba \
  /private/tmp/tow-nd3-m2-roundtrip-poc.bps \
  /private/tmp/tow-nd3-m2-roundtrip-poc-applied.gba

PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 \
  games/tales-of-the-world-narikiri-dungeon-3/tools/extract_strings.py \
  /private/tmp/tow-nd3-m2-roundtrip-poc-applied.gba --skip-identity-check
```

命令輸出只作 metadata／hash／count receipt；所有 `/private/tmp` outputs 都不可加入
Git。
