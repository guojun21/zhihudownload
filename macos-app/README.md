# macOS 原生应用版本 - 知乎视频下载器

这是使用 Swift + SwiftUI 重新编写的原生 macOS 应用版本，相比 Electron + React 版本有以下优势：

## ✨ 优势

- **原生性能**: 直接使用 macOS 系统框架，性能更优秀
- **内存占用少**: Swift 原生编译，相比 Electron 内存占用少
- **原生外观**: 完全遵循 macOS 设计语言和 UI 惯例
- **启动快速**: 无需加载 Node.js 运行时和 Chromium
- **系统集成**: 直接集成 macOS 的文件系统、权限管理等

## 🚀 快速开始

### 方式 1: 使用 Xcode（推荐）

```bash
# 打开 macOS 应用
open /path/to/ZhihuDownloader.xcodeproj

# 或者直接编译并运行
xcodebuild -scheme ZhihuDownloader -configuration Release
```

### 方式 2: 使用 Swift Package Manager

```bash
# 编译
swift build -c release

# 运行
.build/release/ZhihuDownloader
```

### 方式 3: 使用 Make（如果有 Makefile）

```bash
make build
make run
```

## 📋 前置要求

- macOS 13.0 或更高版本
- Xcode 14.0 或更高版本
- Swift 5.9 或更高版本
- Python 后端服务已启动（运行 `python3 api_server.py`）

## 🔧 开发

### 启动后端服务

```bash
cd ..
python3 api_server.py
```

### 运行应用

在 Xcode 中按 `Cmd + R` 运行，或使用命令行：

```bash
swift build
.build/debug/ZhihuDownloader
```

## 📦 应用功能

- ✅ URL 输入和视频解析
- ✅ 多清晰度选择下载
- ✅ 实时进度显示
- ✅ Chrome Cookie 自动读取
- ✅ 自定义输出目录选择
- ✅ 下载队列管理
- ✅ 错误提示和状态显示

## 🎨 UI 特点

- macOS Big Sur+ 设计风格
- 原生控件和交互体验
- 深色/浅色模式自适应
- 符合 macOS 人机界面指南（HIG）

## 📝 Project Structure

```
macos-app/
├── Package.swift                 # Swift Package 配置
├── Sources/
│   ├── ZhihuDownloaderApp.swift # App 入口
│   ├── ContentView.swift         # 主UI视图
│   ├── Models.swift              # 数据模型（可选分离）
│   └── Services/                 # API 服务（可选分离）
└── Tests/                        # 单元测试
```

## 🔌 API 接口

应用通过 HTTP 与后端服务通信，确保后端服务在 `http://127.0.0.1:5124` 运行。

### 主要 API 端点

- `POST /api/parse` - 解析视频
- `POST /api/download` - 开始下载
- `GET /api/progress/:id` - 获取下载进度
- `GET /api/check-cookies` - 检查认证状态

## 🐛 故障排除

### 应用无法启动
- 检查 Xcode 是否已安装：`xcode-select --install`
- 检查 Swift 版本：`swift --version`
- 重建项目：`xcodebuild clean && xcodebuild build`

### 后端连接失败
- 确保 Python 服务器已启动
- 检查服务器地址：`curl http://127.0.0.1:5124/api/check-cookies`

### UI 显示不正常
- 检查 macOS 版本是否 ≥ 13.0
- 尝试 `xcodebuild clean` 清理缓存

## 📖 相关文档

- [Swift 官方文档](https://developer.apple.com/swift/)
- [SwiftUI 文档](https://developer.apple.com/documentation/swiftui/)
- [macOS 应用开发指南](https://developer.apple.com/design/human-interface-guidelines/macos/)

