# 下一步（新 Agent）：按文件 A 搜图并写回词库

## 输入

- 关键词文件 A：`a1-b2/packs/image_search_queries_demo20.json`
- 待填图词库：`a1-b2/packs/demo_a1_20.deword`（`image.path` 为空，`status=pending`）

## 任务

1. 读取文件 A 的每条 `search_en`
2. 用 **Pixabay / Pexels**（优先）或 Openverse / Wikimedia 搜索首张合适图  
   - 不要用 Unsplash 做批量本地下载  
   - 需 API Key 时向用户要，或先用 Openverse/Wikimedia（可无 Key）
3. 下载 → 裁剪约 4:3 → 压成 WebP（约 15–40KB，最长边 480–720）
4. 保存为词库内 `images/{word_id}.webp`
5. 更新 `words.json` 里对应词的 `image.path/source/status`
6. 重新打包 `demo_a1_20.deword`

## 代理

本机可用 HTTP 代理：`http://127.0.0.1:10809`
