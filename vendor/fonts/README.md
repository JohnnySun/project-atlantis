# 開源字庫來源

Project Atlantis 將第三方字庫與自有程式碼分開管理。每個來源必須固定版本、
保留原授權，並在遊戲構建中記錄實際使用的字符子集。

| 來源 | 引入方式 | 用途 | 授權 |
| --- | --- | --- | --- |
| [Fusion Pixel Font](https://github.com/TakWolf/fusion-pixel-font) | Git submodule | 8／10／12px 泛中日韓主字庫 | SIL OFL 1.1；構建程式 MIT |
| [Ark Pixel Font](https://github.com/TakWolf/ark-pixel-font) | Git submodule | `zh_cn`、`zh_tw`、`zh_hk`、`zh_tr` 地區字形 | SIL OFL 1.1；構建程式 MIT |
| [GNU Unifont](https://unifoundry.com/unifont/) | 官方發佈檔直接保存 | 16×16 Unicode 覆蓋後備 | SIL OFL 1.1 或 GPL-2.0-or-later + Font Exception |

初始化或更新 Git 子模組：

```sh
git submodule update --init --recursive
```

字庫不是自動混合。某款遊戲選用或修改字形時，必須生成來源與缺字報告，
並遵守對應字庫的授權條件。
