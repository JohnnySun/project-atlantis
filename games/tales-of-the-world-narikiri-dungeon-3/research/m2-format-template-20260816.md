# M2 control-only format template edge（2026-08-16）

## 發現與分離規則

既有 8,938 筆 strict Shift-JIS/NUL extractor 只接受至少兩個文字 unit；本回合
沿已鎖定 parser caller 做固定 literal 驗證，找到一種不同資料類型：

- code literal file `0x0AEF1C` 的值是 `0x081474C0`，在 reviewed literal set 中
  只有 1 個引用；
- `0x080AEEE0` 先經 `0x08001640`，並另經 `0x08001660→0x08001640`，最後進
  `0x080025CC` parser；
- file `0x1474C0` 是 NUL 結尾的 control-only format template，只含 `%k` token，
  不是 strict record boundary；
- 它後面的 `0x1474C4` 才是獨立 strict record
  `sjis:0x1474C4`（text-pool、raw length 21）。目前不能因相鄰就把兩者視為
  同一筆 source 或同一種容量格式。

可重跑工具 [`tools/format_template_probe.py`](../tools/format_template_probe.py)
以 `format:0x1474C0` 的概念 ID 保存這個 template class；metadata receipt
[`research/m2-format-template-metadata.json`](m2-format-template-metadata.json)
只含 token 名稱、長度、位址、hash、caller 與鄰接 record metadata，不含完整日文。

## Confirmed static／negative

這次確認的是 **static template provenance**：固定 ROM pointer、固定 caller chain
與 parser entry 都一致；`strict_ledger_membership=negative-by-boundary` 也是刻意
保留的結果。它補足了「控制 token 可能獨立於 strict text record」的資料模型，
但還沒有任何 mGBA source read watchpoint 命中，也沒有 `%k` 參數語義、RAM output、
glyph 或 VRAM receipt。

因此：

- `%k` 可先列為 parser command token，不可翻成普通文字或刪除；
- `format:0x1474C0` 不加入現有 8,938 筆 strict ledger，除非日後建立並審核
  template-specific extractor／stable ID 規則；
- `sjis:0x1474C4` 仍只是一筆鄰接 record，未證明由這個 `%k` caller 使用；
- runtime template read、runtime source record edge、token semantics、capacity、
  round-trip、translation、BPS 仍是 **unconfirmed**。

下一個最小 runtime 切片是直接 watch `0x081474C0`（而非假設它等同
`0x081474C4`），在 `0x080025CC`／`0x080014F4` 取得 source pointer、formatted
buffer 與 IWRAM writer；若 runtime 權限仍被環境拒絕，需維持這個精確 static
receipt 與 negative boundary。
