# Clean A9HJ storage-form receipt（2026-08-16）

這份 receipt 只記錄 clean ROM 的 pointer／consumer 結構，不輸出 raw script bytes、完整
日文原文或翻譯來源。正式基準固定為 8 MiB A9HJ、CRC32 `3C24ABCC`、SHA-256
`FB388539B95FDAF6009BAD879E9BBB25955DAF8D4D438486A9213D407B2B48CE`。

可重現命令：

```sh
/usr/bin/python3 games/dragon-quest-monsters-caravan-heart/tools/audit_storage_form.py \
  games/dragon-quest-monsters-caravan-heart/roms/base/Dragon_Quest_Monsters_Caravan_Heart_JP_A9HJ.gba
```

## Clean receipt

- storage form：`direct-rom-pointer-pool-plus-mixed-byte-stream`
- 第一層 pointer table：CPU `0x08266240`，8 個 group（`0..7`）
- 三層 pointer pool：83 個 group／variant 組合、37,600 records、4,879 個 unique pointers；
  32,721 筆是重複 pointer record，所有 pointer target 都落在 clean ROM window
- parser entry：`0x08012500`；state literal `0x03002830`；script pointer field `state+0x18`
- normal source read：CPU `0x08012726` 的 clean Thumb signature，直接由 parser path 取 source
  byte，再進入 mixed-byte glyph／control 分支；控制參數另有 24 個 read signatures
- glyph storage：normal table `0x082DF3D4`、alternate pool `0x082E0BD4`

這些證據把目前可安全命名的儲存形式收斂為「ROM 內三層 little-endian CPU pointer pool
指向 mixed-byte stream」，不是固定長度單層字串表。它仍不等同於完整 script decoder：
`compression_status=not-proven-absent`，因為本工具不把 BIOS compression signature 的
嘈雜掃描當成排除證據；`boundary_status=next-pointer-is-candidate-only`，因為 `FF`、jump、
bank、state-dependent controls 與未修改內容的全量 round-trip 尚未完成。這一輪只改善 M1
storage-form 證據，不勾選完整 control／boundary／encoder gate。
