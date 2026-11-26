# 词库包生成（pack-builder）

从 Anki apkg / 脚本流水线生成 A1–B2 的 `.deword` 词库包（词条、中英释义、例句、音频、配图）。

## 目录要点

| 路径 | 说明 |
|------|------|
| `tools/` | 构建、填图、补中文等脚本 |
| `packs/` | 中间产物与示例 Key 模板 |
| `results/*_final/` | 各等级最终 `.deword`（大文件，默认不进 git，见 Release） |
| `需求文档.md` | 产品需求 |
| `feedback/` | UI 参考图 |

## API Key

复制：

`packs/image_api_keys.example.json` → `packs/image_api_keys.json`

填入 Pixabay / Pexels Key。该文件已被 gitignore，**勿提交**。

## 产出

最终安装用词包请从 GitHub Release **Beta1.0** 下载，勿依赖本目录临时文件。
