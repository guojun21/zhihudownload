#!/usr/bin/env python3
"""
从 Chrome 导出知乎 cookies

这个脚本尝试从 Chrome 浏览器读取知乎的 cookies 并保存为 JSON 文件。
如果自动读取失败，会提供手动导出的说明。

使用方法:
    python export_cookies.py [--output cookies.json]
"""

import json
import argparse
from pathlib import Path


def export_from_chrome():
    """尝试从 Chrome 自动导出 cookies"""
    try:
        import browser_cookie3
        
        print("正在从 Chrome 读取 cookies...")
        print("注意: 可能需要授权访问 macOS Keychain")
        
        cookies = browser_cookie3.chrome(domain_name='.zhihu.com')
        
        cookie_list = []
        for c in cookies:
            cookie_list.append({
                'name': c.name,
                'value': c.value,
                'domain': c.domain,
                'path': c.path,
                'expires': c.expires,
                'secure': c.secure
            })
        
        return cookie_list
        
    except Exception as e:
        print(f"自动读取失败: {e}")
        return None


def show_manual_instructions():
    """显示手动导出 cookies 的说明"""
    print("""
╔══════════════════════════════════════════════════════════════════╗
║                    手动导出 Cookies 说明                          ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  方法 1: 使用 Chrome 扩展                                         ║
║  ────────────────────                                            ║
║  1. 安装 "EditThisCookie" 或 "Cookie-Editor" Chrome 扩展          ║
║  2. 打开 zhihu.com 并登录                                         ║
║  3. 点击扩展图标，导出 cookies 为 JSON                             ║
║  4. 保存为 cookies.json 文件                                      ║
║                                                                  ║
║  方法 2: 使用开发者工具                                            ║
║  ────────────────────                                            ║
║  1. 在 Chrome 中打开 zhihu.com                                    ║
║  2. 按 F12 打开开发者工具                                          ║
║  3. 切换到 Application 标签页                                      ║
║  4. 在左侧找到 Cookies -> https://www.zhihu.com                   ║
║  5. 手动复制以下关键 cookies:                                      ║
║     - z_c0 (最重要的认证 cookie)                                   ║
║     - _xsrf                                                       ║
║     - d_c0                                                        ║
║  6. 创建 cookies.json 文件，格式如下:                               ║
║                                                                  ║
║     [                                                            ║
║       {"name": "z_c0", "value": "你的值", "domain": ".zhihu.com"},║
║       {"name": "_xsrf", "value": "你的值", "domain": ".zhihu.com"},║
║       {"name": "d_c0", "value": "你的值", "domain": ".zhihu.com"} ║
║     ]                                                            ║
║                                                                  ║
║  方法 3: 使用 curl 命令获取 (高级用户)                              ║
║  ────────────────────                                            ║
║  在终端运行以下命令查看 Chrome cookies 数据库:                      ║
║  sqlite3 ~/Library/Application\\ Support/Google/Chrome/Default/  ║
║          Cookies "SELECT name, value FROM cookies WHERE          ║
║          host_key LIKE '%zhihu.com'"                             ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
""")


def main():
    parser = argparse.ArgumentParser(description="导出知乎 cookies")
    parser.add_argument(
        "-o", "--output",
        default="cookies.json",
        help="输出文件路径 (默认: cookies.json)"
    )
    
    args = parser.parse_args()
    
    # 尝试自动导出
    cookies = export_from_chrome()
    
    if cookies and len(cookies) > 0:
        # 保存到文件
        output_path = Path(args.output)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(cookies, f, indent=2, ensure_ascii=False)
        
        print(f"✓ 成功导出 {len(cookies)} 个 cookies 到 {output_path}")
        
        # 检查是否有关键的认证 cookie
        cookie_names = [c['name'] for c in cookies]
        if 'z_c0' in cookie_names:
            print("✓ 包含认证 cookie (z_c0)")
        else:
            print("⚠ 未找到认证 cookie (z_c0)，可能无法下载付费视频")
    else:
        print("\n⚠ 自动导出失败，请尝试手动导出\n")
        show_manual_instructions()


if __name__ == "__main__":
    main()
