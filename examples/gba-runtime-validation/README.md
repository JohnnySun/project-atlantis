# 無版權 GBA runtime QA fixture

`build_fixture.py` 產生兩個 576-byte 的原創假 ROM blob 與一份 matching manifest。
它們不會 boot，專門驗證 static preflight；不包含任何商業遊戲資料。

```sh
fixture_dir="$(mktemp -d /private/tmp/gba-runtime-fixture.XXXXXX)"
python3 examples/gba-runtime-validation/build_fixture.py --out-dir "$fixture_dir"
PYTHONDONTWRITEBYTECODE=1 python3 scripts/gba-runtime-qa.py static \
  "$fixture_dir/case.json" \
  --base-rom "$fixture_dir/base.gba" \
  --candidate-rom "$fixture_dir/candidate.gba"
```

`--fault adjacent|pointer|unterminated|control|overflow|unknown-width|alias`
可產生預期 fail 或 fail-closed unknown 的負例。每次使用新的 `/private/tmp` 目錄，
避免把生成物加入 Git。
