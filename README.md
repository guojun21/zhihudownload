# 知乎视频下载器

基于 YoutubeDownloader 项目风格开发的知乎视频下载工具，支持下载知乎训练营/课程视频。

## 🎉 功能特点

- ✅ **现代化桌面应用** - Electron + React + TypeScript
- ✅ 支持从 Chrome 读取 cookies 进行鉴权（需要 macOS Keychain 授权）
- ✅ 自动解析知乎训练营视频页面
- ✅ 支持多种清晰度选择 (UHD/FHD/HD/SD/LD)
- ✅ 使用 ffmpeg 下载 M3U8 视频流
- ✅ 实时下载进度显示
- ✅ 自动处理文件名和输出目录

## 🚀 快速开始

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

## 前置要求

### 1. Python 3.8+

```bash
python3 --version
```

### 2. FFmpeg

用于下载和合并 M3U8 视频流：

```bash
# macOS
brew install ffmpeg

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

## 使用方法

### 基本用法

```bash
python zhihu_downloader.py "视频页面URL"
```

### 示例

```bash
# 下载训练营视频
python zhihu_downloader.py "https://www.zhihu.com/xen/market/training/training-video/1973778517616523009/1973778517947865002?education_channel_code=ZHZN-cd8085beea05e6d"

# 指定输出目录
python zhihu_downloader.py "视频URL" -o ~/Downloads/zhihu_videos

# 指定清晰度
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

- `uhd`: 超高清 (4K)
- `fhd`: 全高清 (1080p)
- `hd`: 高清 (720p)
- `sd`: 标清 (480p)
- `ld`: 低清 (360p)

## 工作原理

1. **读取 Chrome Cookies**: 使用 `browser_cookie3` 库从 Chrome 浏览器读取知乎的登录 cookies
2. **获取视频信息**: 解析页面获取视频 ID，然后调用知乎 Lens API 获取视频详情
3. **选择最佳清晰度**: 根据用户指定的清晰度选择最合适的视频流
4. **下载视频**: 使用 ffmpeg 下载 M3U8 视频流并合并为 MP4 文件

## 故障排除

### 1. Keychain 授权问题

首次运行时，macOS 会弹出对话框询问是否允许访问 Chrome 的登录数据。请点击「允许」。

如果之前点击了「拒绝」，需要手动重置：
1. 打开「钥匙串访问」应用
2. 搜索「Chrome Safe Storage」
3. 右键点击，选择「访问控制」
4. 添加 Python 或终端应用

### 2. 未找到认证 cookies

确保已在 Chrome 中登录知乎账号，并且是使用 Chrome 浏览器（不是 Safari 或 Firefox）。

### 3. 无法获取视频信息

- 检查是否有权限访问该视频（是否已购买课程）
- 尝试在 Chrome 中刷新页面后重新运行

### 4. ffmpeg 下载失败

- 确保已正确安装 ffmpeg: `brew install ffmpeg`
- 检查网络连接是否正常
- 某些视频可能需要 VPN 访问

## 技术栈

- Python 3.8+
- requests - HTTP 请求
- browser-cookie3 - Chrome cookies 读取
- m3u8 - M3U8 解析
- ffmpeg - 视频流下载和合并

## 免责声明

本工具仅供个人学习和研究使用，请勿用于商业用途或侵犯版权的行为。使用本工具下载视频时，请确保您拥有合法的访问权限。

## License

MIT License
