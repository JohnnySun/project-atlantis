# GBA 翻譯 Agent 共用工具導入

這份短指南供每款 GBA 翻譯 Agent 在自己的 ROADMAP 中逐步採用。遊戲專屬 extractor、
encoder、compression、pointer、codepage、glyph 與 state/navigation 邏輯保持不變。

## 1. ROM identity

不要再新增本作版 header complement／CRC／SHA helper。使用：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 scripts/gba-rom-identity.py \
  games/<game>/roms/base/GAME.gba \
  --expect-size BYTES --expect-game-code CODE --expect-crc32 CRC32 \
  --expect-sha256 SHA256 --output /private/tmp/GAME-identity.json
```

- exit `0`／`status=pass`：所有宣告欄位與 header complement 通過。
- exit `1`／`status=fail`：確定 mismatch。
- exit `2`／`status=unknown`：ROM 無法讀取、過短或 contract 無法判定。
- 若 ROM 確實保留故意失效的 header complement，必須明確使用
  `--allow-invalid-header`；不可默默跳過。

expected value 放在本作 README／manifest，ROM 與輸出報告仍放 `/private/tmp` 或
ignored `work/`。

## 2. mGBA runtime session

先做不啟動 emulator 的 port preflight：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 scripts/gba-runtime-session.py preflight \
  --port PORT --session-report /private/tmp/CASE-preflight.json
```

用 runtime case manifest 啟動一個自有 process：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 scripts/gba-runtime-session.py run CASE.json \
  --rom games/<game>/roms/base/GAME.gba \
  --mgba /absolute/path/to/mgba-headless --port PORT \
  --runtime-report /private/tmp/CASE-runtime.json \
  --session-report /private/tmp/CASE-session.json \
  --log /private/tmp/CASE-mgba.log
```

需要 emulator flags 時重複傳入 `--mgba-arg=VALUE`。對 source-fixed port build，
`--port` 要填實際 compiled port；工具會檢查實際 listener PID，不相信 CLI 宣告。

Session report 的 pass 只表示：port preflight、ROM command、child identity 與 sole
listener ownership 成立。遊戲 QA 的 pass/fail/unknown 仍以 runtime report 為準。
工具只在 PID、PPID、start time、command 全部仍吻合時終止 child；不使用 `pkill`，
也不接管其他 Agent 的 listener。

## 3. 採用順序

1. 新 probe 先改用 identity CLI；舊 helper 不必在同一回合大規模刪除。
2. 有 machine-readable runtime manifest 的 case 改用 session owner。
3. 本作 probe 保留 breakpoint、watchpoint、register setup、state/navigation 和 decoder。
4. 報告仍需 target＋adjacent、capability exercised/unproven、evidence level 與 exit code。
5. 穩定後才逐步淘汰本作的 `runtime_readiness.py`、shell `lsof`/PID trap、重複 hash
   helper；不要在有並行 dirty WIP 時做機械式全目錄改寫。

## 4. 不可替代的本作工作

共用工具不會猜文字位置、codepage、控制碼、glyph identity、pointer、壓縮、容量或
可達畫面。這些仍須由本作 extractor/adapter/manifest 證明；遇到 unknown 應保留
unknown，而不是放寬 identity、adjacent 或 runtime capability gate。
