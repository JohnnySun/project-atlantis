# 《黄金太阳 开启的封印》汉化修订工作区

本目录用于研究和修订 2024 年 12 月 8 日发布的《黄金太阳 开启的封印》新汉化公开测试版，并生成可复现、可校验的通用 GBA 补丁构建。

## 当前状态

- 日版原 ROM 已通过发布说明要求的 CRC32、MD5 和 SHA-1 校验。
- 官方公开测试版 BPS 已成功应用，BPS 的源、目标和补丁 CRC32 均通过。
- 已抽取并核对日文／中文各 11,115 条文本索引；未发现结构性漏译。
- 已定位新版直接字符串表、自定义中文码页及字体渲染钩子；Unicode 映射与逐句校对仍在进行。

## 目录

- `roms/base/`：日版原 ROM 和原始压缩包，仅限本地使用，不进入 Git。
- `roms/build/`：当前及后续构建产物，仅限本地使用，不进入 Git。
- `upstream/2024-public-beta/`：原始 BPS、汉化说明和附带文档，仅限本地使用。
- `tools/bps_apply.rb`：带源、目标和补丁 CRC32 验证的 BPS1 应用器。
- `research/unfinished-scope.md`：公开测试版已知的未完成范围与边界。
- `research/audit-20260814.md`：字符串完整性与程序改动的首轮二进制审计。
- `ROADMAP.md`：后续逆向、校对、测试和发布步骤。

## 基准校验

| 文件 | 大小 | CRC32 | MD5 | SHA-256 |
| --- | ---: | --- | --- | --- |
| 日版原 ROM | 8,388,608 | `fb96d9de` | `cf33e45e59b0ee3801b5cf18a9e58524` | `088bedae4bad8b67e87ff10035a898d3639f3182d486fe5a5d113bab223e0a26` |
| 2024 公开测试版 ROM | 11,594,160 | `d54a0ae9` | `7e64b85b584995c32bc0b349f31cc79e` | `f566de927b4ccf95e55686553db3089c26b842158d49a2a91472a8b6ba1419bc` |
| 上游 BPS | 981,631 | `de428ef4`（BPS 内置） | `918956dccc019995b108b55629578388` | `666bbfa5210d4ee2835c901f4f362727492f6ac414cda7a75de2f6c18bd06486` |

## 重建公开测试版

```sh
ruby tools/bps_apply.rb \
  roms/base/Ougon_no_Taiyou_Hirakareshi_Fuuin_JP_clean.gba \
  'upstream/2024-public-beta/黄金太阳开启的封印_2024新汉化版(公开测试版)_20241208_汉化补丁.bps' \
  roms/build/golden-sun-cn-public-beta.gba
```

构建后必须再次确认目标 CRC32 为 `d54a0ae9`，否则不得作为有效测试构建使用。

## 测试构建原则

ROM、个人存档、实验构建和本机路径不进入公开仓库。测试前应核对输入与构建产物的哈希，并保留上一份已验证构建；不要修改或删除 `.sav`、`.srm` 等存档。
