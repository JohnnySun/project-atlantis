# v0.20 IPS 工程偵察（2026-08-16）

這份記錄只保存外部 patch 的工程摘要；IPS 與套用後 ROM 都留在本機，不進 Git。英文
內容不是日版原文來源，也沒有把 patch 的大段文字抄入專案。

## 外部參考與雜湊

- 專案頁：[Summoner's Lineage patch](https://www.blade2187.com/projects/summoners-lineage/)
- 版本說明：[Summoner's Lineage v0.20](https://www.blade2187.com/2025/02/10/summoners-lineage-v0-20/)
- 本機下載的 v0.20 ZIP SHA-256：
  `04e380aab5a4b37c28989764a73daddaed5c77c7c4661b56d12f38c43068d4f2`
- ZIP 內 `srke020.ips` SHA-256：
  `1ec997c16d32706acbfef3e02642b59ca63cc6afef4d83d09e71ce4224dc5f7e`
- 本機讀出的 patch readme SHA-256：
  `442c39d6235c6736895ea57c96e74e75e51580debdd90ff0212dd186b3503308`

公開說明把 v0.20 定位為部分 patch／後續工程修正，特別提到英文構造字串可能超出
原本日文較短的 buffer，戰鬥 action string 的儲存位置尤其需要注意。這是回插設計的
風險提示，不是本專案可以直接沿用的格式證明。

## 本機套用結果

把 IPS 套到 clean A9PJ image 後，patched image 的標頭仍是 `TOW SUMMLINE`／`A9PJ`，
大小為 `8,730,574` bytes，CRC32 `19faca60`，SHA-256
`aa41a6f24eb21d07b05a3d34a2a436cd47105497d0c6e4fef9a97e8281212804`。

clean／patched byte diff 的摘要：

- 8,251 個變更區段、378,567 個變更 bytes。
- 變更分布於原檔 `0x000000..0x3fffff`，另有少量約 `0x7fc230` 的差異。
- 新增 payload 從 `0x800000` 延伸至 `0x8537ce`；前段可連續驗證 29 個 GBA LZ77
  blocks，最後一個 block chain 結束在約 `0x804617`，之後是未壓縮的字型樣資料與
  16-bit 資料。
- `probe_patch_pointer_rewrites.py` 在 4-byte 對齊、clean 舊值為 GBA ROM pointer、
  patched 新值落在新增 ROM pointer 範圍的條件下，得到 1,616 個 pointer rewrites：
  原檔 bucket `0x000000`／`0x100000`／`0x200000`／`0x300000`／`0x700000` 分別是
  581／109／871／52／3。這些是整體 relocation，不能等同劇本數量。

新增區 `0x800000` 起的 LZ77 blocks 與原區 pointer 改寫可證明 patch 具備自有資源／
資料佈局；但要判定哪一部分是劇本文字，仍須用日版原始指標、執行期讀取與 glyph／
codepage 交叉驗證。

## 不採用的推論

- 不把 patch 的英文句子當作 `source.text` 或日文翻譯依據。
- 不把所有新 pointer 都標成文字；至少有一批明確指向 LZ77 圖像／字型資源。
- 不因新增區看見 16-bit 數值就假設是 ASCII、Shift-JIS 或可直接轉 Unicode；其碼元與
  控制碼仍需透過字形與 runtime 證據確認。
- 不把 patch author 提到的 buffer overflow 修正直接移植到 A9PJ 回插器；先建立 clean
  ROM 的自有 decoder／encoder 與長度驗證。
