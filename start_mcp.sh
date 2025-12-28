#!/bin/bash
# 知乎视频下载器 - MCP 自动启动脚本
# Cursor 会调用这个脚本自动启动服务

cd "$(dirname "$0")"

# 如果服务已在运行就杀掉重启
pkill -f "mcp-server" 2>/dev/null

# 启动 MCP 服务
exec ./mcp-server

