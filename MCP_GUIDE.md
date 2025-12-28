# 🎬 知乎视频下载器 - MCP 服务文档

## 📡 服务地址
```
http://127.0.0.1:5125
```

---

## 🛠️ 可用工具

### 1️⃣ 下载视频 (`download_video`)

**描述**: 下载知乎视频为 MP4 格式（默认最高清晰度）

**请求示例**:
```bash
curl -X POST http://127.0.0.1:5125/mcp/call_tool \
  -H "Content-Type: application/json" \
  -d '{
    "name": "download_video",
    "input": {
      "url": "http://zhihu.com/xen/market/training/...",
      "output_path": "/Users/oasmet/Downloads"
    }
  }'
```

**响应示例**:
```json
{
  "result": {
    "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "status": "已启动下载任务"
  }
}
```

**参数**:
- `url` (必填): 知乎视频 URL
- `output_path` (可选): 输出路径，默认 `~/Downloads`

---

### 2️⃣ 转录视频 (`transcribe_video`)

**描述**: 将视频转录为文本（包括音频提取和 Whisper 转录）

**请求示例**:
```bash
curl -X POST http://127.0.0.1:5125/mcp/call_tool \
  -H "Content-Type: application/json" \
  -d '{
    "name": "transcribe_video",
    "input": {
      "video_path": "/Users/oasmet/Downloads/video.mp4",
      "language": "zh"
    }
  }'
```

**响应示例**:
```json
{
  "result": {
    "task_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
    "status": "已启动转录任务"
  }
}
```

**参数**:
- `video_path` (必填): MP4 视频文件路径
- `language` (可选): 语言代码，默认 `zh` (中文)

---

### 3️⃣ 查看进度 (`get_progress`)

**描述**: 获取下载或转录任务的实时进度

**请求示例**:
```bash
# 查看下载进度
curl -X POST http://127.0.0.1:5125/mcp/call_tool \
  -H "Content-Type: application/json" \
  -d '{
    "name": "get_progress",
    "input": {
      "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "task_type": "download"
    }
  }'

# 查看转录进度
curl -X POST http://127.0.0.1:5125/mcp/call_tool \
  -H "Content-Type: application/json" \
  -d '{
    "name": "get_progress",
    "input": {
      "task_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
      "task_type": "transcribe"
    }
  }'
```

**下载任务响应示例**:
```json
{
  "result": {
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "status": "downloading",
    "percentage": 75,
    "speed": "2.5 MB/s",
    "elapsed_time": 120,
    "file_path": "/Users/oasmet/Downloads/video_a1b2c3d4.mp4",
    "video_url": "http://zhihu.com/...",
    "quality": "hd"
  }
}
```

**转录任务响应示例**:
```json
{
  "result": {
    "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
    "status": "transcribing",
    "percentage": 50,
    "stage": "正在转录...",
    "elapsed_time": 300,
    "video_path": "/Users/oasmet/Downloads/video.mp4",
    "mp3_path": "/Users/oasmet/Downloads/video.mp3",
    "txt_path": "/Users/oasmet/Downloads/video.txt"
  }
}
```

**参数**:
- `task_id` (必填): 任务 ID
- `task_type` (必填): 任务类型 - `download` 或 `transcribe`

---

## 📊 任务状态说明

### 下载任务状态
- `pending`: 等待中
- `downloading`: 下载中 (0-99%)
- `completed`: 下载完成 (100%)
- `failed`: 下载失败

### 转录任务状态
- `extracting_audio`: 提取音频中 (10%)
- `transcribing`: 转录中 (50-99%)
- `completed`: 转录完成 (100%)
- `failed`: 转录失败

---

## 💻 使用示例

### 完整工作流示例

```bash
#!/bin/bash

# 1️⃣ 下载视频
echo "下载视频..."
DOWNLOAD_RESPONSE=$(curl -s -X POST http://127.0.0.1:5125/mcp/call_tool \
  -H "Content-Type: application/json" \
  -d '{
    "name": "download_video",
    "input": {
      "url": "http://zhihu.com/xen/market/training/training-video/...",
      "output_path": "/Users/oasmet/Downloads"
    }
  }')

DOWNLOAD_TASK_ID=$(echo "$DOWNLOAD_RESPONSE" | jq -r '.result.task_id')
echo "✓ 下载任务已启动: $DOWNLOAD_TASK_ID"

# 监控下载进度
while true; do
  PROGRESS=$(curl -s -X POST http://127.0.0.1:5125/mcp/call_tool \
    -H "Content-Type: application/json" \
    -d "{
      \"name\": \"get_progress\",
      \"input\": {
        \"task_id\": \"$DOWNLOAD_TASK_ID\",
        \"task_type\": \"download\"
      }
    }")
  
  STATUS=$(echo "$PROGRESS" | jq -r '.result.status')
  PERCENTAGE=$(echo "$PROGRESS" | jq -r '.result.percentage')
  
  echo "下载进度: $PERCENTAGE% ($STATUS)"
  
  if [ "$STATUS" = "completed" ]; then
    VIDEO_PATH=$(echo "$PROGRESS" | jq -r '.result.file_path')
    echo "✓ 下载完成: $VIDEO_PATH"
    break
  fi
  
  sleep 5
done

# 2️⃣ 转录视频
echo ""
echo "转录视频..."
TRANSCRIBE_RESPONSE=$(curl -s -X POST http://127.0.0.1:5125/mcp/call_tool \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"transcribe_video\",
    \"input\": {
      \"video_path\": \"$VIDEO_PATH\",
      \"language\": \"zh\"
    }
  }")

TRANSCRIBE_TASK_ID=$(echo "$TRANSCRIBE_RESPONSE" | jq -r '.result.task_id')
echo "✓ 转录任务已启动: $TRANSCRIBE_TASK_ID"

# 监控转录进度
while true; do
  PROGRESS=$(curl -s -X POST http://127.0.0.1:5125/mcp/call_tool \
    -H "Content-Type: application/json" \
    -d "{
      \"name\": \"get_progress\",
      \"input\": {
        \"task_id\": \"$TRANSCRIBE_TASK_ID\",
        \"task_type\": \"transcribe\"
      }
    }")
  
  STATUS=$(echo "$PROGRESS" | jq -r '.result.status')
  PERCENTAGE=$(echo "$PROGRESS" | jq -r '.result.percentage')
  
  echo "转录进度: $PERCENTAGE% ($STATUS)"
  
  if [ "$STATUS" = "completed" ]; then
    TXT_PATH=$(echo "$PROGRESS" | jq -r '.result.txt_path')
    echo "✓ 转录完成: $TXT_PATH"
    break
  fi
  
  sleep 10
done

echo ""
echo "🎉 全部完成！"
```

---

## 🔌 集成到 Cursor/Claude

在 `cursor_settings.json` 中添加 MCP 服务配置：

```json
{
  "mcpServers": {
    "zhihu-downloader": {
      "command": "bash",
      "args": [
        "-c",
        "cd /Users/oasmet/Documents/!002Projects/03-media-processing/ZhihuDownloader && ./mcp-server"
      ]
    }
  }
}
```

然后在 Claude 中就可以直接调用：

```
@claude 帮我下载这个知乎视频: http://zhihu.com/xen/market/training/...

然后转录为文本。

最后显示进度。
```

---

## 🚀 启动 MCP 服务

```bash
cd /Users/oasmet/Documents/!002Projects/03-media-processing/ZhihuDownloader

# 启动服务
./mcp-server

# 或者后台启动
./mcp-server &
```

服务启动后会监听 `http://127.0.0.1:5125`

---

## 📋 API 端点总结

| 端点 | 方法 | 描述 |
|------|------|------|
| `/mcp/tools` | GET | 列出所有可用工具 |
| `/mcp/call_tool` | POST | 调用指定工具 |
| `/health` | GET | 健康检查 |

---

## ⚠️ 注意事项

1. **视频清晰度**: 目前默认下载最高清晰度 (hd)
2. **转录语言**: 默认中文 (zh)，支持其他语言代码
3. **输出路径**: 默认保存到 `~/Downloads`
4. **并发限制**: 支持多个任务同时进行
5. **长时间任务**: 转录可能需要 20-30 分钟，建议使用后台任务

---

