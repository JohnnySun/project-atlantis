# GBA runtime validation smoke receipt — 2026-08-16

本 receipt 只保存 ROM／manifest／report／render 的雜湊與 bounded metadata；ROM、save state、
raw memory、畫面與完整原文均未加入版本控制。兩次執行都使用全新、自有的 mGBA PID，runner
連線前驗證 listener PID 等於該次 `$!`，結束後只回收該 PID。

## Emulator identity

- upstream mGBA source commit: `afd6f14eaf8bd35214ed3fb9dc69a92bfc3877a9`
- local-only change: GDB listener fixed to `127.0.0.1:40731`
- headless binary SHA-256: `96b63c18bca90d51c1f8ef4aa3e4f980bed24934bb441bb571b479f807cf2f46`
- source、binary、ROM、manifests 與完整 reports 均留在 `/private/tmp` 或 ignored ROM 路徑

## Shining Soul I — natural menu/text consumer

- ROM identity: 8 MiB, game code `AHUJ`, SHA-256
  `7adebc47af58a7cb12c6e862482e3fd1b2cb82aab2dc3a556ac93f9e78df6b28`
- manifest SHA-256: `8fd81535c311fa8455ff303d742e817eaf1da7017ec4ce9938526ce56b0ed362`
- report SHA-256: `08c9716e90b4a58e91de35780cf33bdb0d678f0fba8fed10a3bd1bf338dc2657`
- verdict: `pass`, runner exit `0`, report checker `pass`
- boot predicate: `DISPCNT == 0x1240`
- input: three KEYINPUT read-watchpoint sequences; every event hit `0x04000130`
- consumer: breakpoint `0x0800E8BC`, normalized PC exact match; bounded `r0` source region
  `0x02003324 + 40`, SHA-256
  `e3a2106f89554a59c64d0b2443e2c719133bcdea7f7e6089a298bdf692a628a7`
- render: final BG0 SHA-256
  `b3324c5c048bc908e17705aa01aa12f5e1fdbc0e38caf26ea6b057388af65760`;
  OAM SHA-256 `6a62bdf51fc4d12ec563aa48232055ca59c6bf4ab99a8ff24adbcb122a3642bf`,
  13 visible objects
- assertions: title→mode VRAM changed; save→job VRAM changed; visible OAM positive
- required capabilities all exercised; `unproven=[]`
- owned PID `74564`; listener ownership and cleanup confirmed

## Sangokushi Eiketsuden — structurally distinct BG/Shift-JIS case

- ROM identity: 4 MiB, game code `B3EJ`, SHA-256
  `d61e284ba882cfba6b960b147bbdd0df642c402a8ed2adce3ccb9b837f0c97b0`
- manifest SHA-256: `c19b0c8f03f85ef3bc72c4315f03f0534ae2b03f49a029efe4e118a80f69245b`
- report SHA-256: `2e6a5c1d54428065b1fded84eab3abce177b16f06b6d2293e21d368335a51952`
- verdict: `pass`, runner exit `0`, report checker `pass`
- boot predicate: `DISPCNT == 0x1E40`
- input: START through KEYINPUT read watchpoint at `0x04000130`, consumer PC `0x0805CF5E`
- target region: `0x08078528 + 14`, SHA-256
  `c7ac47044e9576475f854841981b18ae20eca25ad41df403164ee6307b1aecca`
- adjacent guard: `0x08078536 + 16`, SHA-256
  `83aea5ea6d4f27a973af63352cc1719b08fc98553434e9b77510a3480574b908`
- target and adjacent hashes were unchanged before/after input
- pre-input BG0/BG2 hashes:
  `f52d5bb7376b14c19eefec90d7ce2e10f4cd51a4caf43597f8bf2b154f1d5188`,
  `55bd5580e9eab55728a3371e201a627162f2a0167965e2510fcab6fd92dcd31d`
- post-input BG0/BG2 hashes:
  `19e0f2e35a4a530886c8c7fb9a152bbd2c4b32149378e508ec9d9c1077ad4b49`,
  `3d83bf9f17a983f3a26ec40a8940f089a4efba966241f5712dc83fba91fa7966`
- required capabilities all exercised; `unproven=[]`
- owned PID `76621`; listener ownership and cleanup confirmed

## Reproduction boundary

The copyright-free fixture matrix was rerun with the final code. `none` produced `pass/0`;
`adjacent`, `pointer`, `unterminated`, `control`, `control-arity`, `encoding`, `overflow`, and
`alias` each produced a definite `fail/1`; `unknown-width` produced fail-closed `unknown/2`.
An intentionally missing fixture path also produced `unknown/2`, confirming that absent evidence
cannot be mistaken for a pass.

The ignored manifests pin ROM identity but are intentionally not committed. A later acceptance Session follows
`docs/technical/gba-runtime-validation.md`「後續驗收 Session：短流程」：recreate a local case,
run `validate-manifest`, launch an owned emulator, verify listener PID ownership, run `runtime`, validate the
report with the Skill checker, and retain only hashes/metadata.
