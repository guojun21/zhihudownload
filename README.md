# 知乎视频下载器 | Zhihu Video Downloader

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![Electron](https://img.shields.io/badge/Electron-Desktop_App-47848F.svg)](https://www.electronjs.org/)
[![React](https://img.shields.io/badge/React-18-61DAFB.svg)](https://reactjs.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0-3178C6.svg)](https://www.typescriptlang.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> 🎬 下载知乎训练营、知乎课程、知乎视频的桌面工具 | Download Zhihu training videos, courses and lectures

基于 YoutubeDownloader 项目风格开发的**知乎视频下载工具**，支持下载知乎训练营/课程视频。提供现代化桌面应用和命令行两种使用方式。

## ✨ 功能特点 | Features

- 🖥️ **现代化桌面应用** - Electron + React + TypeScript 构建
- 🔐 **自动读取 Cookies** - 支持从 Chrome 读取 cookies 进行鉴权
- 📺 **多清晰度支持** - 4K/1080p/720p/480p/360p 自由选择
- 🎯 **M3U8 视频流下载** - 使用 ffmpeg 高效下载合并
- 📊 **实时进度显示** - 下载进度一目了然
- 🗂️ **智能文件命名** - 自动处理文件名和输出目录

## 📸 截图 | Screenshots

<!-- 如果有截图可以在这里添加 -->
<!-- ![App Screenshot](./screenshots/app.png) -->

## 🚀 快速开始 | Quick Start

### 方式 1: 桌面应用（推荐）

```bash
# 进入前端目录
cd electron-app

# 安装依赖
npm install

# 启动应用（开发模式）
npm run dev:electron
```

### 方式 2: 命令行工具

```bash
# 安装 Python 依赖
pip install -r requirements.txt

# 运行下载器
python zhihu_downloader.py "视频URL"
```

## 📋 前置要求 | Prerequisites

### 1. Python 3.8+

```bash
python3 --version
```

### 2. FFmpeg

用于下载和合并 M3U8 视频流：

```bash
# macOS
brew install ffmpeg

# Windows (使用 Chocolatey)
choco install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg

# 验证安装
ffmpeg -version
```

### 3. Python 依赖

```bash
cd ZhihuDownloader
pip install -r requirements.txt
```

### 4. Chrome 浏览器登录和 Cookies

**重要**: 下载付费/私有视频需要认证 cookies。有两种方式获取：

#### 方式 1: 自动从 Chrome 读取（推荐）

1. 确保已在 Chrome 浏览器中登录知乎账号
2. 首次运行时会弹出 macOS Keychain 授权对话框，请点击「允许」

#### 方式 2: 手动导出 Cookies

如果自动读取失败，可以手动导出：

1. 安装 Chrome 扩展 "EditThisCookie" 或 "Cookie-Editor"
2. 打开 zhihu.com 并登录
3. 点击扩展图标，导出 cookies 为 JSON
4. 保存为 `cookies.json` 文件
5. 使用 `-c cookies.json` 参数指定 cookies 文件

或者运行辅助脚本查看详细说明：
```bash
python export_cookies.py
```

## 📖 使用方法 | Usage

### 基本用法

```bash
python zhihu_downloader.py "视频页面URL"
```

### 示例

```bash
# 下载训练营视频
python zhihu_downloader.py "https://www.zhihu.com/xen/market/training/training-video/xxx"

# 指定输出目录
python zhihu_downloader.py "视频URL" -o ~/Downloads/zhihu_videos

# 指定清晰度 (1080p)
python zhihu_downloader.py "视频URL" -q fhd

# 不使用 Chrome cookies (仅下载免费视频)
python zhihu_downloader.py "视频URL" --no-cookies
```

### 命令行参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `url` | 知乎视频页面 URL 或视频 ID | 必填 |
| `-o, --output` | 输出目录 | 当前目录 |
| `-q, --quality` | 视频清晰度 (uhd/fhd/hd/sd/ld) | hd |
| `-c, --cookies` | cookies 文件路径 (JSON 格式) | 无 |
| `--no-cookies` | 不使用任何 cookies | False |

### 清晰度说明

| 选项 | 分辨率 | 说明 |
|------|--------|------|
| `uhd` | 4K | 超高清 |
| `fhd` | 1080p | 全高清 |
| `hd` | 720p | 高清 |
| `sd` | 480p | 标清 |
| `ld` | 360p | 低清 |

## 🔧 工作原理 | How it Works

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Chrome Cookies │────▶│  Zhihu Lens API │────▶│  M3U8 视频流    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                        │
                                                        ▼
                                                ┌─────────────────┐
                                                │  FFmpeg 下载    │
                                                │  合并为 MP4     │
                                                └─────────────────┘
```

1. **读取 Chrome Cookies**: 使用 `browser_cookie3` 库从 Chrome 浏览器读取知乎的登录 cookies
2. **获取视频信息**: 解析页面获取视频 ID，然后调用知乎 Lens API 获取视频详情
3. **选择最佳清晰度**: 根据用户指定的清晰度选择最合适的视频流
4. **下载视频**: 使用 ffmpeg 下载 M3U8 视频流并合并为 MP4 文件

## 🛠️ 技术栈 | Tech Stack

### 后端 (Python)
- **Python 3.8+** - 核心语言
- **requests** - HTTP 请求
- **browser-cookie3** - Chrome cookies 读取
- **m3u8** - M3U8 解析
- **ffmpeg** - 视频流下载和合并

### 前端 (Electron)
- **Electron** - 桌面应用框架
- **React 18** - UI 框架
- **TypeScript** - 类型安全
- **Vite** - 构建工具

## ❓ 故障排除 | Troubleshooting

<details>
<summary><b>1. Keychain 授权问题</b></summary>

首次运行时，macOS 会弹出对话框询问是否允许访问 Chrome 的登录数据。请点击「允许」。

如果之前点击了「拒绝」，需要手动重置：
1. 打开「钥匙串访问」应用
2. 搜索「Chrome Safe Storage」
3. 右键点击，选择「访问控制」
4. 添加 Python 或终端应用
</details>

<details>
<summary><b>2. 未找到认证 cookies</b></summary>

确保已在 Chrome 中登录知乎账号，并且是使用 Chrome 浏览器（不是 Safari 或 Firefox）。
</details>

<details>
<summary><b>3. 无法获取视频信息</b></summary>

- 检查是否有权限访问该视频（是否已购买课程）
- 尝试在 Chrome 中刷新页面后重新运行
</details>

<details>
<summary><b>4. ffmpeg 下载失败</b></summary>

- 确保已正确安装 ffmpeg: `brew install ffmpeg`
- 检查网络连接是否正常
- 某些视频可能需要 VPN 访问
</details>

## 🤝 贡献 | Contributing

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建你的特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交你的更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开一个 Pull Request

## ⚖️ 免责声明 | Disclaimer

本工具仅供个人学习和研究使用，请勿用于商业用途或侵犯版权的行为。使用本工具下载视频时，请确保您拥有合法的访问权限。

## 📄 License

[MIT License](LICENSE)

---

⭐ 如果这个项目对你有帮助，请给个 Star 支持一下！

**关键词**: 知乎下载, 知乎视频下载, 知乎课程下载, 知乎训练营下载, zhihu downloader, zhihu video downloader, m3u8 downloader, video downloader, 视频下载器
