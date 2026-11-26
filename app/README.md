# 德词轮刷 · App（NochMal）

Android 客户端源码。显示名：**德词轮刷**，版本 **Beta1.0**。

## 技术栈

- Kotlin + Jetpack Compose + Material 3
- 本地词库包导入（`.deword` = zip：`manifest.json` / `words.json` / `audio/` / `images/`）
- 进度存储于 App 私有目录 `files/progress/`

## 构建

```powershell
cd app
# 需要 JDK 17
.\gradlew.bat assembleDebug
```

输出：`app/build/outputs/apk/debug/app-debug.apk`

## 模块说明

- `app/src/main/java/com/deutsch/vocab/`：UI、QuizViewModel、PackRepository
