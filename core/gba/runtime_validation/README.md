# Manifest-driven GBA QA

這個 package 把 static ROM checks 與 mGBA/GDB runtime evidence 合成 fail-closed report。
完整設計與證據邊界見 `docs/technical/gba-runtime-validation.md`。

```sh
PYTHONDONTWRITEBYTECODE=1 python3 scripts/gba-runtime-qa.py --help
```

模組：

- `manifest.py`：strict built-in manifest loader；
- `static_checks.py`：ROM、change range、target/adjacent、pointer/alias、record/layout；
- `runtime.py`：bounded GDB actions、KEYINPUT hook、memory/register injection、render receipt；
- `result.py`：`pass`／`fail`／`unknown` reduction 與 exit code；
- `cli.py`：`validate-manifest`、`static`、`runtime`。

Runtime runner 只連到呼叫者提供的 local port；它不搜尋、附加或終止未知 process。
