#!/usr/bin/env python3
"""
知乎训练营视频流获取工具

使用方法:
1. 在浏览器中打开知乎并登录
2. 打开开发者工具 (F12)
3. 切换到 Network 标签
4. 刷新视频页面
5. 找到任意请求，复制 Cookie 请求头的值
6. 运行此脚本并粘贴 cookie

或者直接编辑下方的 COOKIES 变量
"""

import requests
import json
import re
from urllib.parse import urlparse

# ============ 在这里粘贴你的 cookie ============
# 从浏览器开发者工具中复制 Cookie 请求头的值
COOKIES = """
粘贴你的 cookie 到这里
"""
# =============================================

# 视频页面 URL
VIDEO_URL = "https://www.zhihu.com/xen/market/training/training-video/1973778517616523009/1973778517947865002"

# 从页面数据中提取的视频 ID
VIDEO_ID = "4zbweJq7bVyP6FeOy6FMVyqjFQ4ooFeo46bRe46fFe4b6FV_yqbFW4oFFe4h6be24qGReyzFFeZZx_6EC"
SECTION_ID = "1973778517947865002"
PRODUCT_ID = "1973778517616523009"


def parse_cookies(cookie_string):
    """解析 cookie 字符串"""
    cookies = {}
    for item in cookie_string.strip().split(';'):
        if '=' in item:
            key, value = item.strip().split('=', 1)
            cookies[key.strip()] = value.strip()
    return cookies


def get_video_stream():
    """获取视频流地址"""
    
    session = requests.Session()
    
    # 设置 cookies
    if COOKIES.strip() and COOKIES.strip() != "粘贴你的 cookie 到这里":
        cookies = parse_cookies(COOKIES)
        for name, value in cookies.items():
            session.cookies.set(name, value, domain='.zhihu.com')
        print(f"✓ 已设置 {len(cookies)} 个 cookies")
        
        # 检查关键 cookie
        if 'z_c0' in cookies:
            print("✓ 找到认证 cookie (z_c0)")
        else:
            print("⚠ 未找到认证 cookie (z_c0)，可能无法访问付费视频")
    else:
        print("⚠ 未设置 cookies，请编辑脚本添加 cookies")
        print("   或者使用交互模式输入")
        cookie_input = input("\n请粘贴你的 cookie (或按回车跳过): ").strip()
        if cookie_input:
            cookies = parse_cookies(cookie_input)
            for name, value in cookies.items():
                session.cookies.set(name, value, domain='.zhihu.com')
            print(f"✓ 已设置 {len(cookies)} 个 cookies")
    
    # 设置请求头
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": VIDEO_URL,
        "Origin": "https://www.zhihu.com",
    })
    
    print(f"\n正在获取视频信息...")
    print(f"视频 ID: {VIDEO_ID}")
    
    # 尝试多个 API 端点
    api_endpoints = [
        # Lens API
        f"https://lens.zhihu.com/api/v4/videos/{VIDEO_ID}",
        f"https://lens.zhihu.com/api/videos/{VIDEO_ID}",
        # 知乎主站 API
        f"https://www.zhihu.com/api/v4/videos/{VIDEO_ID}",
        # 训练营专用 API
        f"https://www.zhihu.com/api/v4/market/training/sections/{SECTION_ID}/video",
        f"https://www.zhihu.com/api/infinity/training/video/{SECTION_ID}",
    ]
    
    for api_url in api_endpoints:
        print(f"\n尝试 API: {api_url}")
        try:
            resp = session.get(api_url, timeout=15)
            print(f"状态码: {resp.status_code}")
            
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    print(f"✓ 获取到 JSON 响应")
                    
                    # 检查是否有播放列表
                    playlist = data.get('playlist', {}) or data.get('playlist_v2', {})
                    if playlist:
                        print(f"\n可用清晰度:")
                        for quality, info in playlist.items():
                            if isinstance(info, dict) and 'play_url' in info:
                                print(f"  {quality}: {info.get('width', '?')}x{info.get('height', '?')}")
                                print(f"    URL: {info['play_url'][:80]}...")
                        return playlist
                    else:
                        print(f"响应内容: {json.dumps(data, ensure_ascii=False)[:500]}")
                except json.JSONDecodeError:
                    print(f"非 JSON 响应: {resp.text[:200]}")
            else:
                content_type = resp.headers.get('content-type', '')
                if 'json' in content_type:
                    try:
                        error = resp.json()
                        print(f"错误: {json.dumps(error, ensure_ascii=False)}")
                    except:
                        print(f"响应: {resp.text[:200]}")
                else:
                    print(f"响应: {resp.text[:100]}")
                    
        except requests.RequestException as e:
            print(f"请求失败: {e}")
    
    print("\n" + "="*60)
    print("未能获取视频流地址")
    print("\n可能的原因:")
    print("1. 未登录或 cookies 已过期")
    print("2. 未购买该课程")
    print("3. API 已更新")
    print("\n建议操作:")
    print("1. 在浏览器中打开视频页面")
    print("2. 打开开发者工具 -> Network")
    print("3. 播放视频，查找 .m3u8 或 .mp4 请求")
    print("4. 复制视频流地址")
    
    return None


def try_get_from_page():
    """尝试从页面获取视频信息"""
    session = requests.Session()
    
    if COOKIES.strip() and COOKIES.strip() != "粘贴你的 cookie 到这里":
        cookies = parse_cookies(COOKIES)
        for name, value in cookies.items():
            session.cookies.set(name, value, domain='.zhihu.com')
    
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9",
    })
    
    print(f"\n正在获取页面: {VIDEO_URL}")
    
    try:
        resp = session.get(VIDEO_URL, timeout=15)
        print(f"状态码: {resp.status_code}")
        
        if resp.status_code == 200:
            # 尝试从页面中提取视频信息
            # 查找 JSON 数据
            json_match = re.search(r'"playlist"\s*:\s*(\{[^}]+\})', resp.text)
            if json_match:
                print(f"找到 playlist 数据: {json_match.group(1)[:200]}...")
            
            # 查找 m3u8 链接
            m3u8_match = re.findall(r'https?://[^"\']+\.m3u8[^"\']*', resp.text)
            if m3u8_match:
                print(f"\n找到 M3U8 链接:")
                for url in m3u8_match[:5]:
                    print(f"  {url}")
                return m3u8_match
                
    except Exception as e:
        print(f"请求失败: {e}")
    
    return None


if __name__ == "__main__":
    print("="*60)
    print("知乎训练营视频流获取工具")
    print("="*60)
    
    # 方法1: 通过 API 获取
    playlist = get_video_stream()
    
    if not playlist:
        # 方法2: 从页面获取
        try_get_from_page()
    
    print("\n" + "="*60)
    print("完成")

