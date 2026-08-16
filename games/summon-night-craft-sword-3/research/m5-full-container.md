# B3CJ full type-2 container coverage receipt

這是 M5.5 後發布 gate 的 static engineering slice，不是新的翻譯批次。新增的
`tools/rebuild_full_container.py` 只接受固定 clean B3CJ ROM，枚舉 type-2
directory 的全部 79 個 entry，將 zero-span alias 與 non-zero payload 分開，對每個
唯一 non-zero PSI3 payload 做 parser/encoder no-op、deterministic GBA LZ77
recompress、既有 span capacity guard 與 zero-fill。ROM、完整 source table、重建
ROM、BPS 與 summary 都留在 ignored `work/`。

## 可重跑命令

```sh
PYTHONDONTWRITEBYTECODE=1 python3 \
  games/summon-night-craft-sword-3/tools/rebuild_full_container.py \
  games/summon-night-craft-sword-3/roms/base/B3CJ-jp-from-zip.gba \
  --output games/summon-night-craft-sword-3/work/m5-full-container-rebuilt.gba \
  --summary-output games/summon-night-craft-sword-3/work/m5-full-container-summary.json \
  --bps-output games/summon-night-craft-sword-3/work/m5-full-container.bps \
  --bps-applied-output games/summon-night-craft-sword-3/work/m5-full-container-applied.gba
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
  -s games/summon-night-craft-sword-3/tools \
  -p 'test_rebuild_full_container.py' -v
```

固定 ROM identity：B3CJ、32 MiB、CRC32 `12afae5d`、SHA-256
`39bc4cf448106aa4b8cdde235632ffb57432c4b1919c8843510b70b3787fad2d`。

## Receipt

| contract | result |
| --- | --- |
| type-2 entries | `79`，其中 `68` 個 non-zero payload、`11` 個 zero-span entries |
| unique positive payload groups | `68`；所有 positive spans non-overlapping |
| zero-span alias clusters | `2,3,4,5 → 6`；`9,10 → 11`；`26,27,28,29,30 → 31` |
| PSI3 stream no-op | `79/79` directory entries round-trip；original／encoded aggregate SHA-256 `6692fc24b14d9b225edaf7484a2d977af7e2e4a46580ca5be8313b3c5a9cf705` 相同 |
| source record re-encode | logical `361/361`；unique positive-payload records `235` |
| opaque／rejected structure | opaque tokens `269`、rejected marker candidates `1`；均原樣保留，不猜語意 |
| payload rebuild | `68/68` capacity guards 通過；directory byte-identical；差異 `24507` bytes 全在 positive payload spans |
| BPS | `26147` bytes；SHA-256 `56c4f35752ef14dd7db6fb8c530b664c041e0535556e5d6f5bdc3bb8790c807e`；apply byte-identical；applied ROM SHA-256 `830d7bf3e755b5628f4bd63ca05b7a90cef5bf2e85bb8ccb3f0c2140bffe4042` |

這個 receipt 將 semantic no-op coverage 從含文字的 13 resources／11 groups 擴展
到固定 type-2 table 的所有 non-zero PSI3 payload；它沒有修改任何翻譯 target，
也沒有把 zero-span alias 當成可獨立重建的 resource。

## Boundary

這不是 translated release encoder：變長 target 的選擇、未知 VM／排版語意、一般化
pointer relocation、header／checksum policy、font／palette／VRAM／OAM runtime
coverage 與畫面可讀性仍未證實。八筆 ledger 仍為 `zh-TW`／`ai_draft`，不得以此
receipt 宣稱完整翻譯或可發布 patch。
