#!/bin/bash

# 知乎视频下载器 - macOS 原生应用启动脚本

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "🚀 知乎视频下载器"
echo "================================"

# 检查后端服务
echo "📍 检查后端服务..."
if ! curl -s http://127.0.0.1:5124/api/check-cookies > /dev/null 2>&1; then
    echo "⚠️  后端服务未启动，开始启动后端..."
    cd "$PROJECT_DIR"
    python3 api_server.py &
    PYTHON_PID=$!
    sleep 2
    
    if ! curl -s http://127.0.0.1:5124/api/check-cookies > /dev/null 2>&1; then
        echo "❌ 后端服务启动失败！"
        echo "请手动运行: python3 api_server.py"
        exit 1
    fi
    echo "✅ 后端服务已启动 (PID: $PYTHON_PID)"
fi

# 编译和运行应用
echo ""
echo "📦 编译应用..."
cd "$SCRIPT_DIR"

if command -v xcodebuild &> /dev/null; then
    echo "✅ 使用 Xcode 构建..."
    xcodebuild -scheme ZhihuDownloader -configuration Release
else
    echo "✅ 使用 Swift 构建..."
    make build
fi

echo ""
echo "🎬 启动应用..."
make run

# 清理
if [ ! -z "$PYTHON_PID" ]; then
    echo ""
    echo "🛑 关闭后端服务..."
    kill $PYTHON_PID 2>/dev/null || true
fi

echo ""
echo "✅ 完成！"

