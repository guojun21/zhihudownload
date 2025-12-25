.PHONY: help build run clean debug release test lint

# 帮助
help:
	@echo "知乎视频下载器 - macOS 原生应用"
	@echo ""
	@echo "可用命令:"
	@echo "  make build       - 编译应用（Debug 模式）"
	@echo "  make release     - 编译应用（Release 模式）"
	@echo "  make run         - 运行应用"
	@echo "  make debug       - 以 Debug 模式编译并运行"
	@echo "  make clean       - 清理编译产物"
	@echo "  make test        - 运行测试"
	@echo "  make lint        - 运行代码检查"
	@echo "  make xcode       - 在 Xcode 中打开项目"
	@echo ""

# 变量
BUILD_DIR := .build
APP_NAME := ZhihuDownloader
SCHEME := ZhihuDownloader
CONFIGURATION_DEBUG := Debug
CONFIGURATION_RELEASE := Release

# 编译 (Debug)
build: clean
	@echo "📦 编译 $(APP_NAME) (Debug 模式)..."
	swift build -c debug
	@echo "✅ 编译完成"

# 编译 (Release)
release: clean
	@echo "📦 编译 $(APP_NAME) (Release 模式)..."
	swift build -c release
	@echo "✅ 编译完成"

# 编译并运行 (Debug)
debug: build
	@echo "🚀 运行 $(APP_NAME)..."
	.build/debug/$(APP_NAME)

# 运行 (Release)
run: release
	@echo "🚀 运行 $(APP_NAME)..."
	.build/release/$(APP_NAME)

# 清理
clean:
	@echo "🧹 清理编译产物..."
	rm -rf $(BUILD_DIR)
	rm -rf build
	@echo "✅ 清理完成"

# 用 Xcode 打开
xcode:
	@echo "📂 在 Xcode 中打开项目..."
	open -a Xcode "$(CURDIR)/ZhihuDownloader.xcodeproj"

# 运行测试
test:
	@echo "🧪 运行测试..."
	swift test

# 代码检查
lint:
	@echo "🔍 运行代码检查..."
	@echo "提示: 请使用 Xcode 的内置分析工具"
	@echo "快捷键: Shift + Cmd + B"

# 安装依赖 (检查环境)
check-env:
	@echo "✓ Swift: $$(swift --version)"
	@echo "✓ macOS: $$(sw_vers -productVersion)"
	@which xcode-select > /dev/null && echo "✓ Xcode 命令行工具已安装" || echo "✗ 需要安装 Xcode 命令行工具"

# 显示帮助
.DEFAULT_GOAL := help

