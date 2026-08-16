# GBA 翻譯共用能力審計

日期：2026-08-17

本文件追蹤八個同時進行的日版 GBA 翻譯專案，目標是把已由多款遊戲獨立證明的
方法收斂到共用 Skill、SOP 與工具，同時避免把任何一款遊戲的 offset、codepage、
compression、pointer 或 glyph identity 誤放進 `core/`。

## 驗收路線圖

- [x] 讀取八款遊戲的 README、ROADMAP、最近提交與完整檔案 inventory。
- [x] 盤點 `research/`、`tools/`、tests、translation ledger 與共用 core 的引用。
- [x] 找出第一組跨三款以上的重複實作：ROM identity/header complement/hash guard。
- [x] 找出共同 runtime blocker：mGBA process、listener、port race、PID ownership。
- [x] 實作 game-agnostic ROM identity 與 runtime session ownership 工具。
- [x] 完成兩個 Skill 的 baseline／新版 eval 與機器可讀結果。
- [ ] 將新工具導入八個 agent，收集至少三款實際使用回報。
- [ ] 完成最終 repository safety、core tests、Skill eval 與 adoption review。

## 專案矩陣

| 專案 | 已證明的文字／資源形狀 | 可共用的發現 | 必須留在本作 |
| --- | --- | --- | --- |
| `super-robot-taisen-d` | 直接 Shift-JIS 池、窄／寬固定 stride glyph、局部同長回插 | strict source hash、全 corpus no-op、target＋adjacent、BPS apply、consumer reroute | A6SJ pool、8/12px layout、slot formula、wide identity |
| `tales-of-the-world-narikiri-dungeon-3` | 五個 Shift-JIS 候選窗、state 4→7、argument-injected parser/glyph edge | bounded navigation、natural 與 controlled 分欄、ACK/register-write evidence | B3TJ windows、state machine、parser/formatter 位址與 token 語義 |
| `summon-night-craft-sword-3` | PSI3/LZ77 type-2 resources、record VM、resource relocation、八筆 cumulative batch | alias/span guard、semantic no-op rebuild、changed＋untouched re-extract、停止重複小批次的 release gate | B3CJ PSI3、VM opcode、resource table、font slot allocation |
| `fire-emblem-6-binding-blade` | map/code-unit/font-source 初始化鏈，仍在 source/layout gate | content/arity fail-closed、source initializer trace、target/adjacent manifest | AFEJ map、font planes、event/text control semantics |
| `shin-megami-tensei-2` | queue/dispatch/LZ77/OBJ resource 與 semantic manifest，尚無 stable source table | RAM dispatch 必須 runtime read、resource/record adjacency、static/runtime evidence 分離 | SMT2 queue、skill/demon records、writer/resource layout |
| `dragon-quest-monsters-caravan-heart` | A9HJ clean ROM、E0/E1 glyph banks、bounded message/menu batches | raw-span identity replay、control consumption context、局部 batch gate | script records、bank mapping、message pointer/consumer |
| `tales-of-the-world-summoners-lineage` | bounded fixed UI rows、known-screen static decoder、兩筆 ledger | known UI ground truth、renderer cross-check、bounded reinsertion | A9PJ UI tables、start/menu state、full map/event format |
| `sangokushi-eiketsuden` | 多文字池與 108 筆 ledger、自然 title/menu runtime、consumer 尚未對上 | process/listener readiness、input receipt與文字 consumer 分離、source-safe story ledger | B3EJ pools、event index、Table B、formatter/consumer semantics |

## 已確認的重複造輪子

### 應進 `core/gba/` 或 `scripts/`

1. ROM identity：至少四款自行實作 `gba_header_checksum`，且公式曾分成正確的
   `-sum-0x19` 與錯誤的 `0x19-sum`。CRC32、SHA-256、title、game code、maker code
   亦散落在大量 probe。現在統一由 `core/gba/rom_identity.py` 與
   `scripts/gba-rom-identity.py` 提供。
2. runtime process ownership：《英傑傳》已有本作版 readiness helper，其他專案則
   在 shell、probe 或文件中重寫 port/PID/listener 邏輯。現在由
   `core/gba/runtime_session.py` 與 `scripts/gba-runtime-session.py` 統一執行
   preflight、exact child identity、sole listener、runner exit propagation 與安全清理。
3. GDB packet、standard capture、BG/OAM render 已存在 `core/gba/`；新的遊戲工具
   應只保留地址、state、sequence 與解碼 adapter，不再複製 transport/renderer。
4. source／working／ledger、BPS create/apply 已有 core 實作。重複 wrapper 只有在
   game-specific container/re-extract contract 需要 orchestration 時才合理。

### 應更新 SOP／Skill

1. ROM reconnaissance 的第一個 gate 應是共用 identity CLI；expected identity 留在
   本作文件或 manifest，ROM path 留在本機。
2. `natural`、`state-assisted`、`controlled-consumer`、`static-only` 必須分欄；
   listener success、input ACK、畫面 hash、consumer hit 各自不能互相替代。
3. 完成一個代表性同長 static batch 後，不應持續增加同型短句；應切換至下一個
   release gate，例如自然 consumer、layout、changed glyph、完整 corpus 或術語審核。
4. target record 必須和 adjacent/guard 一起檢查；只看到 framebuffer 變化不能證明
   指定譯文已正確顯示。
5. RAM pointer/table 是 runtime state，不可用 ROM scan 假裝能靜態恢復。

### 不應泛化

- 任一遊戲的 ROM offset、function address、state number、input sequence。
- Shift-JIS、glyph-index、VM opcode 或 control-code 的語義。
- pointer width/alignment、compression、resource alias 或 relocation policy。
- glyph identity、font capacity、line width、screen reachability。
- 單一遊戲研究報告中的 provisional semantic label。

這些資料應留在 `games/<game>/tools/`、manifest 或 research，由共用工具讀取明確
contract，而不是寫死在 core。

## Inventory 證據

審計時八個目錄共有 440 個 tool、212 個 test、264 份 research 與 53 份 translation
ledger／batch 檔。AST inventory 顯示跨遊戲重複的 `sha256`、`gba_header_checksum`、
`read_u32`、`write_jsonl`、`parse_sequence`、`register_snapshot` 與 report builder；
但只有 ROM identity 與 runtime ownership 已具備明確、穩定且不帶格式假設的共用
contract。JSONL、sequence 與 report helper 暫不因名稱相同就泛化，需第二輪確認
欄位語義也相同。

## Skill 評測結論

`gba-runtime-validation-workspace/iteration-4` 以四個代表性 prompt 比較修改前 snapshot
與新版 Skill。control arity 與 fail-closed receipt 在兩組均通過，證明既有 SOP 沒有
退化；ROM identity 在兩組也都能找到自解釋 CLI。真正有辨識力的是 owned-listener
case：baseline 重新手寫約 180 行 shell launcher，新版直接採用
`scripts/gba-runtime-session.py`，保留同等的 listener／PID-reuse 安全條件，同時移除
每個遊戲重造 lifecycle code 的成本。

系統 `/usr/bin/python3` 為 3.9.6，而 skill-creator viewer 使用 Python 3.10 的
`dict | None` 型別語法，因此本輪未啟動互動 viewer。標準化 output summary、assertion
grading、benchmark 與 analyzer notes 仍保存於 ignored workspace；此為 viewer 相容性
限制，不是略過 eval。

## 後續候選

- Manifest-driven localization release chain：串接 identity、ledger、re-extract、BPS、
  static/runtime case 與 repository safety；先觀察三款採用結果，再決定是否另建 CLI。
- Source-safe terminology evidence schema：目前各遊戲 TSV/Markdown 欄位不同；要先
  確認來源 URL、majority/deferred、string ID 與 target term 的共同最小集合。
- Input-sequence parser/register snapshot：多款有相似函式，但 state semantics 差異大，
  優先讓 runtime manifest 表達，不急著抽成自由格式 helper。
