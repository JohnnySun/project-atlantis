# A9PJ M31 BIOS resource trace／ROM→VRAM 陰性（2026-08-16）

M31 重用 `/private/tmp` 的既有 headless mGBA binary，只開啟 GBA BIOS debug log，
不建立新的遊戲專用 runtime tool，也不把沒有 GDB listener 的執行誤寫成 reader hit。
ROM、trace raw 與任何 snapshot 都留在 `/private/tmp/tow-a9pj-m31-rom-vram/`。

## bounded trace

```sh
/private/tmp/atlantis-mgba-headless-build/mgba-headless \
  -l 0 -C logLevel.gba.bios=16 -C logLevel.gba.dma=0 -g \
  /private/tmp/project-atlantis-a9pj.gba \
  > /private/tmp/tow-a9pj-m31-rom-vram/mgba-bios.log 2>&1
```

本次 trace 的私有 log receipt 是 4,459,916 bytes／312,194 lines；`-g` 仍回報
`Debugger: Couldn't open socket`，所以沒有 GDB register、breakpoint、KEYINPUT 或
keyboard gate receipt。這一輪只採用 log 中的 BIOS `SWI 0x12` source/destination
metadata，並以 clean A9PJ ROM 的既有 LZ77 decoder 重算輸出 hash。

另外重用既有 SDL binary 與 `/private/tmp/mgba-port-rewrite.dylib`，將其 GDB 入口
導向本 session 的 `24567`；bounded run 沒有 listener、log 也沒有 `GDBStubListen`
receipt，隨即停止自己的 process。這是 transport availability negative，不是 text
consumer negative；沒有把它和 23901 或其他 session 混用。

## source→destination receipt

trace 有 39 組 distinct `SWI 0x12` source／destination／register tuple。所有輸出都在
private memory 中與已知 name-entry keyboard tile-1／tile-2 hash 比對，掃描每個輸出的
32-byte even offset；source bytes、解壓 bytes 與 raw VRAM 都沒有寫入 repository。

| runtime destination | traced source file offsets | 結果 |
| --- | --- | --- |
| `0x06004020` | `0x1EB044`, `0x1F0388`, `0x29647C`, `0x2966DC`, `0x292B54`, `0x29DDB0`, `0x292928` | 7 組均 `keyboard_exact_offsets=[]`；`0x1EB044` 首 tile 是 reset-stage `02d449…` |
| `0x06004000` | `0x298F84` | `keyboard_exact_offsets=[]` |
| 其他 `0x0600xxxx` | 其餘 31 組 | 與 keyboard charblock 不同 destination，且無 keyboard tile exact match |

`0x1EB044` LZ77 header 是 `10 80 09 00`，decoded size `2432`、decoded SHA-256
`484054709ef0ef4320e8fd95c958cb152a19af928625bfb31dd3928584bbd010`；其輸出 offset
`0` 的 32-byte hash 為 `02d449a31fbb267c8f352e9968a79e3e5fc95c1bbeaa502fd6454ebde5a4bedc`，
與 keyboard tile-1 `b5ae44407e13c9f6c085af00c74f47811dff6afe93020f068bdc33b8c1ff39c2` 不同。

因此 M31 確認的是一批 runtime BIOS decompression resource provenance 與一個可重現的
ROM→VRAM keyboard negative；它沒有確認 keyboard asset 的 source，也沒有把其他
charblock 資源合併到 `0x005E`／`0x0066` font-record CPU path。由於沒有 live reader／
code-unit sequence／scene context，confirmed glyph identity 仍為 0，source table、
ledger、翻譯與回插 gate 維持關閉。

## 下一個最小缺口

需要一個可建立 listener 的 fresh A9PJ runtime，或等價的已授權 input/script capture，
在自然 name-entry gate 命中同一個 text consumer，取得 live stream pointer、code-unit
sequence、scene role 與 destination tile hash；M31 不取代這個缺口。
