# A9PJ M46 terminology／bounded BPS regression receipt（2026-08-16）

M46 把官方角色／產品頁的 research-only 術語矩陣與既有兩條 target plumbing 放在同一
個 QA slice 驗證。沒有新增 ROM、raw source、候選掃描或字型檔；所有 target image、BPS
與 re-extract work files 都留在 `/private/tmp`。

## 術語邊界

官方頁可直接支持角色、職業與系統短詞的日文／語境；矩陣只記錄工作候選與 pending
理由。`ユニット`、`召喚術`、`召喚士`、`遺品`、`クラスチェンジ`、`モンク`、
`マジシャン`、`ファイター`、`ルシファー`、`シャーマン` 尚未取得本作 non-UI
source offset／code-unit sequence，也沒有因官方頁面直接進入 ledger。

## BPS regression

沿用 M33/M34 已核准的 bounded Latin target profiles，重新從 clean A9PJ 建立 target、
套用 BPS，再以 byte comparison 驗證：

| profile | target image SHA-256 | BPS SHA-256 | apply equality | runtime QA |
| --- | --- | --- | --- | --- |
| M32 surname | `1b4ce53cfd2026532d02ca3d2a8e9fb72ec7b5fb7600c69e0c17da6d23a7f9c7` | `4a6078ca3fffbb6b48c2e81f477b22f1f6d373d7c84474435e37ed6bd20f130d` | pass | not run |
| M34 protagonist name | `c0b28bfe039ba828783e9a3ea36398754be31bc080fc7f40861bce1f48d82bcb` | `7aed24815b443895f98815431c59cb2d5ad3b22c7d4a142c1b0882fe0214c7b1` | pass | not run |

第一列 target image 仍是 `8,388,624` bytes，第二列 `8,388,622` bytes；兩者都只改
固定 caller pointer、保留原 source span，並由既有 `m33_target_reinsertion_poc.py`
做 terminator／bounded alphabet／target hash verification。這是 plumbing regression，
不是 CJK encoder、完整 re-extract 或 patched mGBA screen proof。

## 判定

```text
official-terminology-research = pass (pending/candidate only)
existing-bounded-target-profiles = pass (2/2)
bps-apply-byte-equality = pass (2/2)
cjk-target-encoder = false
non-ui-source-coverage = false
patched-runtime-qa = false
```

下一個最小缺口是取得一個可獨立驗證的 non-UI source row／live consumer，或完成不依賴
未授權字型的目標 glyph policy；在此之前不把候選術語批次送入 ledger。
