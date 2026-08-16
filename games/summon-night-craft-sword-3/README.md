# 《召喚夜響曲 鑄劍物語 ～起源之石～》工作區

本目錄只處理日版 GBA 第三代《サモンナイト クラフトソード物語 〜はじまりの石〜》（候選 game code `B3CJ`）。不修改第一代或第二代，也不把 KONKR、Project Advance、ADB 或其他裝置部署問題帶入 Project Atlantis 核心架構。

本作採用 `.agents/skills/gba-localization/SKILL.md` 與 `docs/TRANSLATION-LEDGER.md` 的新遊戲帳本流程：日文原文只在本機 `research/*-decoded.jsonl`，翻譯編輯只在本機 `work/`，可提交資料只使用 `translations/*.jsonl` 的 `source_hash` 形式。ROM、patch、渲染圖、OCR 輸出與大段掃描結果不提交。

## 目前狀態

截至 2026-08-16，已從使用者提供的日版 ZIP 唯讀取出單一 32 MiB ROM，並以 `inspect_rom.py --strict` 證實為 `B3CJ`。M1.5、M2.1、M2.2 與 M2.3 static slices 已完成：依固定的 csm3 callsite 鎖定 type-2 script resource table，對 LZ77／`PSI3` 資源建立有界 extractor，從 13 個 resource ID 可重抽 361 筆真實日文 record；新增控制碼保真 parser、opaque fallback、Shift-JIS source re-encode 與解壓 stream byte-identical round-trip；再由 type-3 `BIT` resource、lookup table、24-byte glyph cell 與固定 codepage samples 建立可重跑的 static renderer、27-slot allocation manifest，以及 2-glyph／2-record 的 fail-closed bounded encoder POC。未命名 VM opcode、palette／runtime VRAM、完整 ROM container rebuild 與翻譯回插仍未完成，尚未開始大批翻譯。完整狀態見 [`research/recon-ledger.md`](research/recon-ledger.md)、[`research/static-format.md`](research/static-format.md)、[`research/m2.1-control-roundtrip.md`](research/m2.1-control-roundtrip.md)、[`research/m2.2-font.md`](research/m2.2-font.md)、[`research/m2.3-poc.md`](research/m2.3-poc.md) 與 [`ROADMAP.md`](ROADMAP.md)。

### ROM metadata／外部比對

| 欄位 | 公開參考值 | 本專案狀態 |
| --- | --- | --- |
| Game code | `B3CJ` | 本機 header 已確認 |
| Header title | `CRAFTSWORD H` | 本機 header 已確認 |
| ROM size | 32 MiB | 本機檔案已確認 |
| CRC32 | `12AFAE5D` | 本機檔案已確認 |
| GBA header checksum | `6B` | stored／calculated 均為 `6B` |
| 本機 SHA-256 | `39bc4cf448106aa4b8cdde235632ffb57432c4b1919c8843510b70b3787fad2d` | 已確認 |
| 公開反編譯 build/reference SHA-1 | `3f5253fcf57e07ce52472bd29a61d16b98a12376` | 只作外部比對，不能代替本機 clean ROM |

這些值來自固定的 [Data Crystal 遊戲頁 oldid=69650](https://datacrystal.tcrf.net/wiki/Summon_Night_Craft_Sword_Monogatari%3A_Hajimari_no_Ishi?oldid=69650) 與 [csm3 commit `7e388ac`](https://github.com/jiangzhengwenjz/csm3/commit/7e388ac861bbac289b1f86dc5b8fa46d47b1a1a2)。若本機檔案不一致，必須保留實際 hash 並標記版號差異，不得直接覆寫或把不同版本混為同一 revision。

## 唯讀偵察

遊戲專用工具只讀檔案，不產生或修改 ROM。ZIP 內的 ROM 已放在被 Git ignore 的 `roms/base/`，不會提交：

```sh
python3 games/summon-night-craft-sword-3/tools/inspect_rom.py --strict \
  games/summon-night-craft-sword-3/roms/base/B3CJ-jp-from-zip.gba
```

它會輸出：

- GBA header title、game code、maker code、revision byte 與 complement checksum。
- 檔案大小、CRC32、MD5、SHA-1、SHA-256。
- 有界的 Shift-JIS 常見詞 probe 命中位置；命中只算線索，不算日文文本。
- ROM 位址指標 run、Thumb `swi` 候選與 GBA 壓縮 header 候選的摘要。

有限量靜態掃描另用：

```sh
python3 games/summon-night-craft-sword-3/tools/scan_static.py \
  games/summon-night-craft-sword-3/roms/base/B3CJ-jp-from-zip.gba \
  --output games/summon-night-craft-sword-3/work/static-report.json
```

它只保留候選 offset、長度、計數、pointer reference、decoder consumed size 與 SHA-256；預設掃描 halfword alignment `0`，Shift-JIS-shaped run 至少 8 個 16-bit units，LZ77／RLE 每種最多嘗試 2048 個 header 且 expanded size 上限為 `0x40000`。`work/static-report.json` 是重跑用 ignored 產物，不是提交內容。

M1.5 的 bounded script extractor 另用：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 games/summon-night-craft-sword-3/tools/extract_static.py \
  games/summon-night-craft-sword-3/roms/base/B3CJ-jp-from-zip.gba \
  --output games/summon-night-craft-sword-3/research/summon-night-craft-sword-3-decoded.jsonl \
  --verify-roundtrip
```

這會驗證固定 ROM 身分，解析 type-2 table `0x1718ffc` 的 79 個 resource ID，解壓 `PSI3` stream，並把不含翻譯的日文原文與結構化控制資料寫入 ignored JSONL；`--verify-roundtrip` 只驗證解壓 PSI3 stream 與 record 層，不宣稱 LZ77／pointer／ROM 回插。工具測試與實際收據見 [`research/m2.1-control-roundtrip.md`](research/m2.1-control-roundtrip.md)；不要將該 JSONL stage。

尚未由 extractor 覆蓋的候選仍必須再經反組譯、ROM-to-VRAM byte match 或 mGBA 執行期讀取確認。共用 `core/gba/capture_runtime.py` 與 renderer 已可用，且共用測試 6 項通過；M2.3 曾先確認高位 `24387` 空閒，再以本作自己的 mGBA PID `26484` 嘗試 `-C ports.qt.gdbPort=24387`，但 mGBA 0.10.5 CLI 仍只 listen 自己的 `2345`。透過該 PID 的 listener 執行 core capture 時，`qSupported:multiprocess+` timeout；程序已停止，沒有 runtime summary 或 raw dump 證據。這次收據記為 `RUNTIME-004`，只限制 live RAM／VRAM／palette／OAM 交叉驗證，不否定已由本機 ROM、固定 pointer table 與 csm3 consumer 重跑的 M1.5／M2.3 靜態結果；不新增遊戲專屬 GDB／dump／renderer。

## M2.2 字型鏈與 static POC

`tools/inspect_font.py` 只接受固定 B3CJ 身分，並逐次驗證 csm3 commit `7e388ac` 對應的本機 function ranges／literal pool。它確認 type-3 resource `id=2` 的 `BIT` payload 位於 file `0x14d5c6c`、glyph base `0x14d5c88`，共有 `0x860` 個 24-byte、12×12 cell；`sub_0800348C` 的 table A/B、zero fallback 與 `glyph_id=value-1` 定址也已由 8 個 identity/addressing samples 交叉驗證。掃描得到 2087 個 strict code units 對應 2087 個 physical slots，安全未引用空白槽是 `0x845..0x85f` 共 27 個；非空但不可尋址的 `0x141..0x15e` 共 30 個不分配。palette、VRAM/OAM arrangement 與 runtime 仍維持獨立 blocked。

只用 repository 已固定的 GNU Unifont 17.0.05 產生兩個 ignored static POC glyph：opaque `ec48`／`ec49` 分別暫映射到 `的`／`你` 的 `0x845`／`0x846`，並用 untouched `0x844` 做鄰接 render。POC 的 table/cell 修改區域共 52 bytes，固定 source 下實際非零 byte diff 為 43；輸出 ROM／PGM／summary 均在 ignored `work/`，不代表翻譯或可發布 patch。來源、SHA-256、授權及 16→12 packing 規則見 [`research/font-sources.md`](research/font-sources.md) 與 [`research/m2.2-font.md`](research/m2.2-font.md)。

重跑 font summary：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 games/summon-night-craft-sword-3/tools/inspect_font.py \
  games/summon-night-craft-sword-3/roms/base/B3CJ-jp-from-zip.gba \
  --source-jsonl games/summon-night-craft-sword-3/research/summon-night-craft-sword-3-decoded.jsonl \
  --summary-output games/summon-night-craft-sword-3/work/m2.2-font-summary.json
```

## M2.3 fail-closed glyph allocation／bounded POC

`research/m2.3-glyph-manifest.json` 固定 B3CJ、M2.1 source-table、GNU Unifont
source hash 與唯一可分配範圍 `0x845..0x85f`。`tools/encode_m2_3_poc.py` 只接受
這些固定輸入，保留既有 mapping，拒絕 source／ROM／font hash mismatch、strict
Shift-JIS collision、重複 code unit／slot、範圍外 slot、未分配 target、長度不符與
resource span capacity overrun；新的 opaque code unit 在 clean ROM 上只可使用
`table_value=0` 的未佔用 entry，patch 後必須重新 lookup 為 mapped，不能把
fallback 或 out-of-resource 當成可用目標。

本切片以 `ec48`／`ec49` 兩個 static POC glyph（暫用 `的`／`你`）及兩筆相同
byte length 的短 record 驗證：resource 22 的 `485/496` 與 resource 25 的
`1652/1664` compressed/span 均符合原容器；font mapping／cell、record、PSI3
stream 均 byte-identical round-trip，patched ROM／PGM／summary 全在 ignored
`work/`。測試也會拒絕重複、strict collision、hash mismatch、fallback／
out-of-resource 狀態與容量超限。完整 hash、stable ID 與 runtime 收據見
[`research/m2.3-poc.md`](research/m2.3-poc.md)。

重跑 M2.3 POC：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 games/summon-night-craft-sword-3/tools/encode_m2_3_poc.py \
  games/summon-night-craft-sword-3/roms/base/B3CJ-jp-from-zip.gba \
  --source-jsonl games/summon-night-craft-sword-3/research/summon-night-craft-sword-3-decoded.jsonl \
  --manifest games/summon-night-craft-sword-3/research/m2.3-glyph-manifest.json \
  --font-source vendor/fonts/unifont/unifont-17.0.05.hex.gz \
  --output games/summon-night-craft-sword-3/work/m2.3-poc.gba \
  --summary-output games/summon-night-craft-sword-3/work/m2.3-poc-summary.json \
  --render-output games/summon-night-craft-sword-3/work/m2.3-poc.pgm
```

這仍是 static POC，不是已審核翻譯、完整 ROM 回插、BPS 或可發布 patch；palette、
writer destination、VRAM/OAM layout 與畫面 glyph 可讀性仍因 `RUNTIME-004` blocked。

## 文字系統研究邊界

外部 [Data Crystal TBL](https://datacrystal.tcrf.net/wiki/Summon_Night_Craft_Sword_Monogatari%3A_Hajimari_no_Ishi/TBL?oldid=53006) 提供主日文字型的 16-bit code-table 線索；本輪已用固定 B3CJ ROM 的多個 `0x0308 ... 0x0000` record 交叉驗證：VM halfword 仍按 little-endian 讀取，但 marker 後的 codepage bytes 必須以記憶體原始順序直接做 strict Shift-JIS decode，不能逐 halfword swap。M2.1 另以 csm3 handler／expression callsite 證實有限控制形狀，未知 word 保留 opaque；這不代表字型與所有 opcode 都已命名，也不能假設第一、二代的格式相同。完整格式見 [`research/static-format.md`](research/static-format.md) 與 [`research/m2.1-control-roundtrip.md`](research/m2.1-control-roundtrip.md)。研究時必須分開記錄：

1. 字串在哪裡、如何分界、是否有指標、壓縮與控制碼如何運作。
2. glyph 的位址／tile 定址是否已找到。
3. 每個 glyph 的 Unicode 身分是否有獨立交叉證據。

目前已建立受限的 `research/summon-night-craft-sword-3-decoded.jsonl` 作為本機原文邊界；OCR 只能作候選證據，不能直接複製到翻譯記錄。已命名控制碼可做 record/stream round-trip，但未知 opcode、字型與完整排版規則確認前，不開始劇情、支線、夥伴、鍛造、戰鬥或道具的翻譯批次。

## 翻譯帳本與術語

本作的翻譯批次必須遵循：

```text
research/*-decoded.jsonl  (本機日文原文，不提交)
        + restore_translations.rb
work/*.jsonl              (本機 source + zh-TW 工作檔，不提交)
        + strip_translations.rb
translations/*.jsonl      (可提交 ledger，只含 source_hash)
```

目標語言固定明寫為 `zh-TW`。專有名詞先查臺灣繁體 Wikipedia、巴哈姆特等多個社群來源，採既有主流寫法；若來源分裂，保留現有選擇並在 review note 說明，不自行創造音譯。既有英文／中文 patch 可參考工程資訊，但不是未審核的日文翻譯來源。

## 完成標準（M2.3 static slice 已達成，翻譯／回插尚未達成）

- clean 日版 ROM 的 header、revision、CRC32、SHA-256 已記錄並可重跑。
- type-2 script table、LZ77、`PSI3` stream、bounded text record、Shift-JIS codepage 與 csm3 consumer 有遊戲專用、可重跑證據。
- 已命名控制碼的參數寬度、opaque fallback、361 筆 source re-encode 與 13 個 resource 的 decoded stream byte-identical round-trip 有收據。
- M2.2 已由本機 callsite／literal、type-3 BIT resource、code-unit lookup、12×12／24-byte cell 與 8 個 identity/addressing samples 證實 static glyph chain；已掃描 2144 slots，保留 27 個明確空槽，並完成不破壞既有 mapping 的 2-glyph static POC。
- M2.3 已固定只允許 `0x845..0x85f` 的 glyph allocation manifest；2 個 opaque POC code unit、2 筆等長短 record 通過 source／ROM／font hash、font mapping／cell、record／PSI3 stream 與原 resource span capacity 的 fail-closed byte-level round-trip。這不等於翻譯或完整 ROM 回插。
- 相同 byte length 的 record-level 原地修改可行；zero padding 縮短 blocked，變長需 resource rebuild；完整 VM、字型、LZ77／pointer encoder 與 ROM 回插仍待建立。
- 至少一個有限量批次通過 `restore → work → strip` 往返與 repository safety check。
- 編碼器／回插器拒絕來源 hash、缺字、控制碼或長度不一致，而不是放寬檢查。
- 重建 ROM 重新抽取吻合；BPS round-trip 與 mGBA 核心畫面回歸另有收據。

目前已完成 clean 日版 ROM 身分／hash、M1.5 靜態 decoder、M2.1 控制碼保真 parser、361 筆 ignored source extraction、M2.2 static font chain／POC 與 M2.3 fail-closed allocation／bounded POC；尚無翻譯、ROM build、BPS、完整 VM／resource rebuild／font insertion 或 runtime QA 收據。
