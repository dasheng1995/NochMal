# 德词轮刷 · NochMal

**中文名：** 德词轮刷  
**英文名：** NochMal  
**版本：** Beta1.0  

NochMal（德语「再来一次」）是一款面向中文用户的 **Android 德语词汇轮刷工具**：用高频词库 + 选择题冲量练习，帮你在短时间内反复过词，而不是拉很长间隔的传统 SRS。

## 为什么做这个 App

背德语单词时，常见矛盾是：

- Anki 等间隔重复很稳，但**单日吞吐偏低**，冲 A1–B2 词量时节奏慢；
- 纯列表死记缺少**即时对错反馈**和**词义场景**；
- 手机上需要**离线可用**、词库可按等级拆分安装，避免安装包过大。

因此 NochMal 的目标是：

1. **高吞吐刷词**：选择题（看词选义）为主，选对进释义，选错标红可继续；
2. **按库隔离**：A1 / A2 / B1 / B2 各自进度（斩 / 未看过 / 不会 / 学习中 / 第几轮）；
3. **斩（Easy）雪藏**：会的词下一轮不再出现；
4. **瘦 App + 外置词库包（`.deword`）**：App 本体轻量，词库（音频 + 强压缩配图 + 中英释义）按需导入。

## 仓库结构（仅开发相关）

| 目录 | 说明 |
|------|------|
| [`app/`](app/) | Android 客户端（Kotlin + Jetpack Compose） |
| [`a1-b2/`](a1-b2/) / `pack-builder/` | 词库包生成流水线（从 apkg/脚本构建 `.deword`） |
| [`release/`](release/) | 本地产出目录说明；**安装包与词库请到 Releases 下载** |

> 个人学习笔记等本地文件不在本仓库中。

## 下载 Beta1.0

请到仓库 **[Releases · Beta1.0](../../releases/tag/Beta1.0)** 下载：

| 文件 | 说明 |
|------|------|
| `NochMal-Beta1.0.apk` | Android 安装包 |
| `NochMal-A1-Beta1.0.deword` | A1 词库包 |
| `NochMal-A2-Beta1.0.deword` | A2 词库包 |
| `NochMal-B1-Beta1.0.deword` | B1 词库包 |
| `NochMal-B2-Beta1.0.deword` | B2 词库包 |

## 安装与运行环境

### 手机要求

- **系统：** Android 8.0（API 26）及以上（已在三星等机型侧载验证；越高版本一般可直接安装）
- **架构：** 常见 ARM64 手机即可
- **权限：** 需允许「安装未知应用」/ 侧载 APK；导入词库时使用系统文件选择器读取 `.deword`
- **网络：** **刷词全程可离线**；仅在你自行跑词库构建脚本拉图时才需要网络与 API Key（Keys 不随仓库分发）

### 安装步骤

1. 从 Release 下载 `NochMal-Beta1.0.apk`，在手机上安装。
2. 下载需要的 `.deword` 词库包到手机（下载目录或任意文件夹）。
3. 打开 **德词轮刷** → **导入词库** → 选中对应 `.deword`。
4. 进入词库 → **开始刷词**。

### 覆盖更新

使用**同一包名**的新 APK **直接覆盖安装**（不要先卸载），本地进度一般会保留。

### 自行编译 App（可选）

- JDK **17**
- Android SDK（compileSdk 35）
- 在 `app/` 目录执行：`.\gradlew.bat assembleDebug`
- 产物：`app/app/build/outputs/apk/debug/app-debug.apk`

## 安全说明

- 仓库**不包含** Pixabay / Pexels 等 API Key。
- 词库构建如需 Key，请本地复制 `a1-b2/packs/image_api_keys.example.json` 为 `image_api_keys.json`（已 gitignore）。

## License

个人学习项目 Beta；第三方音频/图片请遵守其原始许可。词库媒体来源于公开语料与免版税图库流水线，请合理使用。
