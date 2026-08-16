# B3CJ 字型來源與授權固定紀錄

本文件只固定 M2.2 靜態 POC 使用的字型來源與轉換規則，不把大檔字型、生成的 glyph、ROM 或 PGM 圖片複製到本作目錄。字型來源已存在於 repository 的共用 `vendor/`，本切片沒有修改或重新提交它。

## 已固定來源

| 項目 | 固定值 |
| --- | --- |
| 字型 | GNU Unifont `17.0.05`，官方 16×16 `.hex` source |
| repository source | `vendor/fonts/unifont/unifont-17.0.05.hex.gz` |
| 官方 URL | <https://unifoundry.com/pub/unifont/unifont-17.0.05/font-builds/unifont-17.0.05.hex.gz> |
| gzip SHA-256 | `2ae5311c8e123e9e85f5331cd012aa99757071df23243f1487fdbf8f3acd86be` |
| 授權文字 | `vendor/fonts/unifont/LICENSE.txt`、`vendor/fonts/unifont/OFL-1.1.txt` |
| 授權檔 SHA-256 | `1e74cb82bf476843e97c2596297b04219b1a7e51f7238944a8c031cb9401fa87`、`869692af094c57fb7258c57fe26820c759319603321d0ffeb278de3651763ded` |
| repository 來源紀錄 | [`vendor/fonts/unifont/README.md`](../../vendor/fonts/unifont/README.md) |

上列版本、URL、SHA-256 與授權界線沿用 repository 已固定的官方來源紀錄；M2.2 沒有新增網路下載，也沒有把 GNU Unifont 的完整 source 匯入本作 `games/`。實際檔案完整性可用 `vendor/fonts/unifont/README.md` 的 hash 重核。

## B3CJ 轉換規則

1. 讀取 Unifont 16×16 bitmap；每個 source row 是 2 bytes、MSB-first。
2. 以 `src = floor(dst * 16 / 12)` 做 deterministic 16→12 nearest-neighbour downsample。
3. 將 12×12 active bits 放進 B3CJ cell 每列 2 bytes 的高 12 bits，低 4 bits 保持 padding；輸出 cell 固定 24 bytes。
4. M2.2 POC 只把 `ec48`、`ec49` 當作遊戲專用 opaque code unit，分別暫映射到 `的`、`你` 的 POC glyph；這兩個 raw code unit 不是宣稱為日文 Shift-JIS 字元，也不代表已開始翻譯。

這是可重現的 cell packing proof，不是最終字型品質決定。12×12 cell 的版面留白、palette、遊戲實際 VRAM tile arrangement 與 runtime 可讀性仍需後續驗證；沒有把 Unifont 衍生 glyph 宣稱為本作發布資產。

## 重跑與保存界線

```sh
PYTHONDONTWRITEBYTECODE=1 python3 games/summon-night-craft-sword-3/tools/inspect_font.py \
  games/summon-night-craft-sword-3/roms/base/B3CJ-jp-from-zip.gba \
  --font-source vendor/fonts/unifont/unifont-17.0.05.hex.gz \
  --poc-rom games/summon-night-craft-sword-3/work/m2.2-font-poc.gba \
  --poc-render games/summon-night-craft-sword-3/work/m2.2-font-poc.pgm \
  --summary-output games/summon-night-craft-sword-3/work/m2.2-font-poc-summary.json
```

上述 ROM、PGM 與 JSON 都是 ignored work product；只保留本文件的來源／規則與 [`m2.2-font.md`](m2.2-font.md) 的摘要、hash 和 provenance。若未來更換字型，必須另記錄官方版本、URL、source hash、授權文字與轉換規則，不能以未授權或來源不明的大段字型取代。
