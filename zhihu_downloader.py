#!/usr/bin/env python3
"""
知乎视频下载器

用于下载知乎训练营/课程视频，支持从 Chrome 读取 cookies 进行鉴权。

依赖:
    - requests
    - browser_cookie3  (用于从 Chrome 读取 cookies，需要 macOS Keychain 授权)
    - m3u8
    - ffmpeg (系统命令行工具)

使用方法:
    python zhihu_downloader.py <视频页面URL> [--output <输出目录>]

示例:
    python zhihu_downloader.py "https://www.zhihu.com/xen/market/training/training-video/1973778517616523009/1973778517947865002"
"""

import os
import re
import json
import argparse
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse, urljoin
from dataclasses import dataclass

try:
    import requests
except ImportError:
    print("请安装 requests: pip install requests")
    exit(1)

try:
    import browser_cookie3
except ImportError:
    print("请安装 browser_cookie3: pip install browser-cookie3")
    print("注意: 首次运行时需要授权访问 macOS Keychain")
    exit(1)

try:
    import m3u8
except ImportError:
    print("请安装 m3u8: pip install m3u8")
    exit(1)


@dataclass
class VideoInfo:
    """视频信息"""
    video_id: str
    title: str
    duration: int  # 毫秒
    playlist: Dict[str, Any]  # 包含不同清晰度的播放地址


@dataclass
class DownloadOption:
    """下载选项"""
    quality: str  # 清晰度名称，如 'hd', 'sd', 'ld'
    width: int
    height: int
    format: str
    play_url: str
    size: Optional[int] = None


class ZhihuVideoDownloader:
    """知乎视频下载器"""
    
    # 知乎视频 API
    LENS_API_BASE = "https://lens.zhihu.com/api/v4/videos"
    
    # 请求头
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://www.zhihu.com/",
        "Origin": "https://www.zhihu.com",
    }
    
    def __init__(self, use_chrome_cookies: bool = True, cookie_file: str = None):
        """
        初始化下载器
        
        Args:
            use_chrome_cookies: 是否使用 Chrome 的 cookies 进行鉴权
            cookie_file: 手动提供的 cookies 文件路径 (JSON 格式)
        """
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        
        if cookie_file:
            self._load_cookies_from_file(cookie_file)
        elif use_chrome_cookies:
            self._load_chrome_cookies()
    
    def _load_cookies_from_file(self, cookie_file: str):
        """从文件加载 cookies"""
        print(f"正在从文件加载 cookies: {cookie_file}")
        try:
            with open(cookie_file, 'r') as f:
                cookies_data = json.load(f)
            
            for cookie in cookies_data:
                self.session.cookies.set(
                    cookie.get('name'),
                    cookie.get('value'),
                    domain=cookie.get('domain', '.zhihu.com')
                )
            
            print(f"✓ 成功加载 {len(cookies_data)} 个 cookies")
        except Exception as e:
            print(f"⚠ 加载 cookies 文件失败: {e}")
    
    def _load_chrome_cookies(self):
        """从 Chrome 加载 cookies"""
        print("正在从 Chrome 读取 cookies...")
        print("注意: 可能需要授权访问 macOS Keychain，请在弹出的对话框中点击「允许」")
        
        try:
            # 获取知乎相关的 cookies
            cookies = browser_cookie3.chrome(domain_name=".zhihu.com")
            self.session.cookies.update(cookies)
            
            # 验证是否获取到关键的认证 cookies
            cookie_names = [c.name for c in self.session.cookies]
            required_cookies = ["z_c0"]  # 知乎的关键认证 cookie
            
            has_auth = any(name in cookie_names for name in required_cookies)
            if has_auth:
                print("✓ 成功获取认证 cookies")
            else:
                print("⚠ 未找到认证 cookies，可能需要先在 Chrome 中登录知乎")
                
        except Exception as e:
            print(f"⚠ 读取 Chrome cookies 失败: {e}")
            print("请确保已安装 browser-cookie3 并授权访问 Keychain")
    
    def _extract_video_id_from_url(self, url: str) -> Optional[str]:
        """
        从知乎页面 URL 中提取视频 ID
        
        支持的 URL 格式:
        - 直接的 lens video ID (数字或加密格式，不包含 http)
        - https://www.zhihu.com/zvideo/{video_id} - 普通知乎视频
        
        注意: 训练营视频 URL 需要通过 _get_video_info_from_page 获取真正的视频 ID
        """
        # 如果是 URL，解析它
        if url.startswith("http"):
            parsed = urlparse(url)
            
            # 普通知乎视频页面: /zvideo/{video_id}
            if "/zvideo/" in parsed.path:
                path_parts = parsed.path.rstrip("/").split("/")
                for i, part in enumerate(path_parts):
                    if part == "zvideo" and i + 1 < len(path_parts):
                        return path_parts[i + 1]
            
            # 训练营视频 URL 需要通过页面获取，返回 None
            return None
        
        # 如果不是 URL，检查是否是直接的视频 ID
        # 数字 ID 或加密的视频 ID（不含 / 和 :）
        if url.isdigit():
            return url
        
        # 加密的视频 ID 格式：字母数字和下划线，长度较长，不含特殊 URL 字符
        if len(url) > 30 and "/" not in url and ":" not in url:
            return url
        
        return None
    
    def _get_video_info_from_page(self, url: str) -> Optional[Dict[str, Any]]:
        """
        从知乎页面获取视频信息
        
        对于训练营视频，直接从页面解析 MP4 视频流地址
        """
        print(f"正在获取页面信息...")
        
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            # 解码 HTML 实体
            import html as html_module
            html_content = html_module.unescape(response.text)
            
            parsed = urlparse(url)
            
            # 方法1: 直接从页面提取 MP4 视频流地址 (知乎训练营视频)
            # 这是最可靠的方式，因为知乎会在页面中直接嵌入视频地址
            mp4_pattern = r'https://vdn[0-9]*\.vzuu\.com/[^"\'<>\s]+\.mp4\?[^"\'<>\s]+'
            mp4_urls = re.findall(mp4_pattern, html_content)
            
            if mp4_urls:
                print(f"✓ 从页面找到 {len(mp4_urls)} 个视频流")
                
                # 去重并分类
                playlist = {}
                seen = set()
                for mp4_url in mp4_urls:
                    if mp4_url not in seen:
                        seen.add(mp4_url)
                        # 解析清晰度
                        if '/FHD/' in mp4_url:
                            quality = 'fhd'
                            width, height = 1920, 1080
                        elif '/HD/' in mp4_url:
                            quality = 'hd'
                            width, height = 1280, 720
                        elif '/SD/' in mp4_url:
                            quality = 'sd'
                            width, height = 854, 480
                        elif '/LD/' in mp4_url:
                            quality = 'ld'
                            width, height = 640, 360
                        else:
                            quality = 'unknown'
                            width, height = 0, 0
                        
                        if quality not in playlist:
                            playlist[quality] = {
                                'play_url': mp4_url,
                                'format': 'mp4',
                                'width': width,
                                'height': height,
                            }
                
                # 提取章节标题（当前视频名称）
                section_title = ""
                # 更精确的匹配：在 videoInfo 对象中查找 title
                # 匹配结构: "videoInfo": {..., "title": "开班典礼", ...}
                video_info_match = re.search(r'"videoInfo"\s*:\s*\{.*?"title"\s*:\s*"([^"]+)"', html_content, re.DOTALL)
                if video_info_match:
                    section_title = video_info_match.group(1)
                else:
                    # 备用：查找 trainingVideo.data.videoInfo.title
                    training_video_match = re.search(r'"trainingVideo"\s*:\s*\{.*?"videoInfo"\s*:\s*\{.*?"title"\s*:\s*"([^"]+)"', html_content, re.DOTALL)
                    if training_video_match:
                        section_title = training_video_match.group(1)
                    else:
                        # 最后备用：查找任何 title 字段（但排除 course.title）
                        title_match = re.search(r'(?<!"course"\s*:\s*\{[^}]*)"title"\s*:\s*"([^"]+)"', html_content)
                        if title_match:
                            section_title = title_match.group(1)
                
                # 提取课程总体名称
                course_title = ""
                # 查找 product.course.title（训练营课程名称）
                # 匹配结构: "product": {"course": {"title": "课程名称"}}
                product_course_match = re.search(r'"product"\s*:\s*\{[^}]*"course"\s*:\s*\{[^}]*"title"\s*:\s*"([^"]+)"', html_content, re.DOTALL)
                if product_course_match:
                    course_title = product_course_match.group(1)
                else:
                    # 备用：直接查找 course.title
                    course_match = re.search(r'"course"\s*:\s*\{[^}]*"title"\s*:\s*"([^"]+)"', html_content, re.DOTALL)
                    if course_match:
                        course_title = course_match.group(1)
                
                return {
                    "video_id": "direct_mp4",
                    "title": section_title or "zhihu_video",
                    "course_title": course_title,
                    "playlist": playlist,
                    "source": "page_mp4"
                }
            
            # 方法2: 从训练营 API 获取视频信息 (备用)
            if "/training-video/" in parsed.path:
                path_parts = parsed.path.rstrip("/").split("/")
                if len(path_parts) >= 2:
                    section_id = path_parts[-1]
                    
                    api_endpoints = [
                        f"https://www.zhihu.com/api/infinity/training/section/{section_id}",
                        f"https://www.zhihu.com/api/v4/market/training/section/{section_id}",
                    ]
                    
                    for training_api_url in api_endpoints:
                        print(f"尝试 API: {training_api_url}")
                        try:
                            api_response = self.session.get(training_api_url, timeout=30)
                            if api_response.status_code == 200:
                                api_data = api_response.json()
                                resource = api_data.get("resource", {})
                                if resource.get("type") == "video":
                                    video_data = resource.get("data", {})
                                    video_id = video_data.get("id")
                                    if video_id:
                                        print(f"✓ 获取到视频 ID: {video_id[:50]}...")
                                        return {
                                            "video_id": video_id,
                                            "title": api_data.get("title", ""),
                                            "duration": video_data.get("duration", 0),
                                            "source": "training_api"
                                        }
                        except:
                            continue
            
            # 方法3: 从页面 JSON 中提取视频 ID
            patterns = [
                r'"resource"\s*:\s*\{[^}]*"data"\s*:\s*\{[^}]*"id"\s*:\s*"([a-zA-Z0-9_-]{20,})"',
                r'"id"\s*:\s*"([a-zA-Z0-9_-]{40,})"[^}]*"type"\s*:\s*"video"',
                r'"video_id"\s*:\s*"(\d+)"',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, html_content, re.DOTALL)
                if match:
                    video_id = match.group(1)
                    if len(video_id) > 10:
                        print(f"从页面匹配到视频 ID: {video_id[:50]}...")
                        title = ""
                        title_match = re.search(r'"title"\s*:\s*"([^"]+)"', html_content)
                        if title_match:
                            title = title_match.group(1)
                        return {"video_id": video_id, "title": title, "source": "regex"}
            
            print("⚠ 无法从页面中提取视频信息")
            return None
            
        except requests.RequestException as e:
            print(f"⚠ 获取页面失败: {e}")
            return None
    
    def get_video_info(self, video_id: str, title: str = "") -> Optional[VideoInfo]:
        """
        获取视频信息，包括不同清晰度的播放地址
        
        Args:
            video_id: 知乎 Lens 视频 ID (可能是数字 ID 或加密 ID)
            title: 视频标题（可选，用于保存文件名）
            
        Returns:
            VideoInfo 对象，包含视频信息和播放地址
        """
        # 知乎有多种视频 API:
        # 1. 普通视频: https://lens.zhihu.com/api/v4/videos/{numeric_id}
        # 2. 训练营视频: 需要特殊的认证
        
        # 尝试多个 API 端点
        api_urls = [
            f"{self.LENS_API_BASE}/{video_id}",
            f"https://lens.zhihu.com/api/videos/{video_id}",
        ]
        
        for api_url in api_urls:
            print(f"正在尝试 API: {api_url}")
            
            try:
                response = self.session.get(api_url, timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # 检查是否有播放列表
                    playlist = data.get("playlist", {})
                    
                    # 如果没有 playlist，尝试 playlist_v2
                    if not playlist:
                        playlist = data.get("playlist_v2", {})
                    
                    if playlist:
                        # 解析视频信息
                        video_info = VideoInfo(
                            video_id=video_id,
                            title=title or data.get("title", f"zhihu_video_{video_id[:20]}"),
                            duration=data.get("duration", 0),
                            playlist=playlist
                        )
                        return video_info
                    else:
                        print(f"  API 返回成功但没有播放列表")
                else:
                    print(f"  返回状态码: {response.status_code}")
                    
            except requests.RequestException as e:
                print(f"  请求失败: {e}")
            except json.JSONDecodeError as e:
                print(f"  JSON 解析失败: {e}")
        
        # 如果所有 API 都失败，说明可能需要认证
        print("\n⚠ 无法获取视频播放信息")
        print("  可能的原因:")
        print("  1. 这是付费视频，需要登录并购买")
        print("  2. cookies 未正确加载或已过期")
        print("  3. 视频 ID 无效")
        print("\n  提示: 请尝试以下步骤:")
        print("  1. 运行 'python export_cookies.py' 导出 cookies")
        print("  2. 使用 '-c cookies.json' 参数指定 cookies 文件")
        
        return None
    
    def get_download_options(self, video_info: VideoInfo) -> List[DownloadOption]:
        """
        获取视频的下载选项（不同清晰度）
        
        Args:
            video_info: 视频信息对象
            
        Returns:
            下载选项列表
        """
        options = []
        
        playlist = video_info.playlist
        
        # 清晰度优先级
        quality_order = ["uhd", "fhd", "hd", "sd", "ld"]
        
        for quality in quality_order:
            if quality in playlist:
                item = playlist[quality]
                option = DownloadOption(
                    quality=quality,
                    width=item.get("width", 0),
                    height=item.get("height", 0),
                    format=item.get("format", "m3u8"),
                    play_url=item.get("play_url", ""),
                    size=item.get("size")
                )
                if option.play_url:
                    options.append(option)
        
        return options
    
    def _download_m3u8_video(self, m3u8_url: str, output_path: str, 
                             progress_callback=None) -> bool:
        """
        下载 M3U8 视频流
        
        Args:
            m3u8_url: M3U8 播放列表 URL
            output_path: 输出文件路径
            progress_callback: 进度回调函数
            
        Returns:
            是否下载成功
        """
        # 检查 ffmpeg 是否可用
        ffmpeg_path = shutil.which("ffmpeg")
        if not ffmpeg_path:
            print("⚠ 未找到 ffmpeg，请先安装: brew install ffmpeg")
            return False
        
        print(f"使用 ffmpeg 下载视频...")
        print(f"M3U8 URL: {m3u8_url[:100]}...")
        
        # 构建 ffmpeg 命令
        # 添加 headers 以模拟浏览器请求
        cmd = [
            ffmpeg_path,
            "-headers", f"User-Agent: {self.HEADERS['User-Agent']}\r\nReferer: https://www.zhihu.com/\r\n",
            "-i", m3u8_url,
            "-c", "copy",  # 直接复制流，不重新编码
            "-bsf:a", "aac_adtstoasc",  # 处理 AAC 音频
            "-y",  # 覆盖已存在的文件
            output_path
        ]
        
        try:
            # 先调用进度回调，表示开始下载
            if progress_callback:
                progress_callback(1)  # 1% 表示开始
            
            # 运行 ffmpeg，显示进度
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            # 读取 stderr 获取进度信息
            stderr_output = []
            last_progress = 1
            total_duration = None
            
            # 尝试从 M3U8 获取总时长
            try:
                playlist_response = self.session.get(m3u8_url, timeout=10)
                if playlist_response.status_code == 200:
                    # 解析 M3U8 获取总时长（简单估算）
                    content = playlist_response.text
                    duration_match = re.search(r'#EXTINF:([\d.]+)', content)
                    if duration_match:
                        segment_duration = float(duration_match.group(1))
                        segment_count = content.count('#EXTINF:')
                        if segment_count > 0:
                            total_duration = segment_duration * segment_count
            except:
                pass  # 如果无法获取总时长，使用文件大小估算
            
            while True:
                line = process.stderr.readline()
                if not line and process.poll() is not None:
                    break
                if line:
                    stderr_output.append(line)
                    # 检查是否包含时间信息
                    if "time=" in line:
                        # 提取已下载时间
                        time_match = re.search(r'time=(\d{2}):(\d{2}):(\d{2})\.(\d+)', line)
                        if time_match:
                            h, m, s, ms = map(int, time_match.groups())
                            elapsed = h * 3600 + m * 60 + s + ms / 100.0
                            
                            # 计算进度
                            if total_duration and total_duration > 0:
                                progress = min(99, max(1, int(elapsed / total_duration * 100)))
                            else:
                                # 如果没有总时长，使用文件大小估算
                                output_file = Path(output_path)
                                if output_file.exists():
                                    file_size = output_file.stat().st_size
                                    # 简单估算：假设文件会增长到一定大小
                                    # 这里使用一个保守的估算值
                                    estimated_size = 50 * 1024 * 1024  # 50MB 估算
                                    if file_size > 0:
                                        progress = min(99, max(1, int(file_size / estimated_size * 100)))
                                    else:
                                        progress = last_progress + 1 if last_progress < 90 else 90
                                else:
                                    progress = last_progress + 1 if last_progress < 90 else 90
                            
                            if progress > last_progress and progress_callback:
                                progress_callback(progress)
                                last_progress = progress
                            
                            # 使用换行输出，便于 Go 程序按行解析进度
                            print(f"下载进度: {progress}%", flush=True)
            
            print()  # 换行
            
            if process.returncode == 0:
                # 下载完成，调用回调设置为 100%
                if progress_callback:
                    progress_callback(100)
                return True
            else:
                full_stderr = "".join(stderr_output)
                print(f"⚠ ffmpeg 下载失败 (exit code: {process.returncode})")
                if "403 Forbidden" in full_stderr:
                    print("  错误: 访问被拒绝，可能需要登录或无权限访问此视频")
                elif "404 Not Found" in full_stderr:
                    print("  错误: 视频不存在或已被删除")
                else:
                    # 显示最后几行错误信息
                    error_lines = [l for l in stderr_output if l.strip()][-5:]
                    for line in error_lines:
                        print(f"  {line.strip()}")
                return False
                
        except subprocess.SubprocessError as e:
            print(f"⚠ 运行 ffmpeg 失败: {e}")
            return False
    
    def _download_mp4_video(self, url: str, output_path: str,
                            progress_callback=None) -> bool:
        """
        直接下载 MP4 视频
        
        Args:
            url: 视频 URL
            output_path: 输出文件路径
            progress_callback: 进度回调函数
            
        Returns:
            是否下载成功
        """
        try:
            response = self.session.get(url, stream=True, timeout=60)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if progress_callback and total_size > 0:
                            progress = downloaded / total_size * 100
                            progress_callback(progress)
            
            return True
            
        except requests.RequestException as e:
            print(f"⚠ 下载失败: {e}")
            return False
    
    def download_video(self, url_or_id: str, output_dir: str = ".",
                       quality: str = "hd", 
                       progress_callback=None) -> Optional[str]:
        """
        下载知乎视频
        
        Args:
            url_or_id: 知乎视频页面 URL 或视频 ID
            output_dir: 输出目录
            quality: 期望的视频质量 (uhd/fhd/hd/sd/ld)
            progress_callback: 进度回调函数
            
        Returns:
            下载成功时返回输出文件路径，失败返回 None
        """
        # 提取视频 ID
        video_id = None
        page_info = None
        
        # 首先检查是否是直接的视频 ID（不是 URL）
        if not url_or_id.startswith("http"):
            if url_or_id.isdigit() or (len(url_or_id) > 30 and "_" in url_or_id):
                video_id = url_or_id
                print(f"使用直接提供的视频 ID")
        
        if not video_id:
            # 尝试从 URL 提取（仅适用于普通知乎视频）
            video_id = self._extract_video_id_from_url(url_or_id)
            if video_id:
                print(f"从 URL 提取到视频 ID")
        
        if not video_id:
            # 尝试从页面获取（训练营视频需要这种方式）
            print("正在从页面获取视频信息...")
            page_info = self._get_video_info_from_page(url_or_id)
            if page_info:
                video_id = page_info.get("video_id")
                if video_id:
                    print(f"成功从页面获取视频 ID")
        
        if not video_id and not page_info:
            print("⚠ 无法获取视频信息")
            print("  可能的原因:")
            print("  1. 未登录知乎或登录已过期")
            print("  2. 没有购买该课程")
            print("  3. 视频 URL 格式不正确")
            return None
        
        # 获取视频标题（如果有的话）
        video_title = ""
        if page_info:
            video_title = page_info.get("title", "")
        
        # 如果页面解析时已经获取到了 playlist，直接使用
        if page_info and page_info.get("source") == "page_mp4" and page_info.get("playlist"):
            print(f"✓ 使用页面直接解析的视频流")
            video_info = VideoInfo(
                video_id="direct_mp4",
                title=page_info.get("title", video_title) or "zhihu_video",
                duration=0,
                playlist=page_info.get("playlist", {})
            )
        else:
            # 显示视频 ID（截断以便阅读）
            if video_id:
                display_id = video_id[:50] + "..." if len(video_id) > 50 else video_id
                print(f"视频 ID: {display_id}")
            
            # 获取视频信息
            video_info = self.get_video_info(video_id, video_title) if video_id else None
        if not video_info:
            print("⚠ 无法获取视频信息")
            return None
        
        print(f"视频标题: {video_info.title}")
        print(f"视频时长: {video_info.duration / 1000:.0f} 秒")
        
        # 获取下载选项
        options = self.get_download_options(video_info)
        if not options:
            print("⚠ 没有可用的下载选项")
            return None
        
        print(f"\n可用清晰度:")
        for opt in options:
            print(f"  - {opt.quality}: {opt.width}x{opt.height} ({opt.format})")
        
        # 选择最佳清晰度
        selected_option = None
        quality_order = ["uhd", "fhd", "hd", "sd", "ld"]
        
        # 首先尝试找到请求的清晰度
        for opt in options:
            if opt.quality == quality:
                selected_option = opt
                break
        
        # 如果没找到，选择最高清晰度
        if not selected_option:
            for q in quality_order:
                for opt in options:
                    if opt.quality == q:
                        selected_option = opt
                        break
                if selected_option:
                    break
        
        if not selected_option:
            selected_option = options[0]
        
        print(f"\n选择清晰度: {selected_option.quality} ({selected_option.width}x{selected_option.height})")
        
        # 准备输出文件
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 生成文件名：总体名字-课名字
        course_title = ""
        section_title = video_info.title
        
        # 如果从页面获取到了课程名称，使用它
        if page_info and page_info.get("course_title"):
            course_title = page_info.get("course_title")
        
        # 清理文件名中的非法字符
        def clean_filename(name):
            cleaned = re.sub(r'[<>:"/\\|?*]', '_', name)
            return cleaned[:100]  # 限制长度
        
        if course_title:
            # 格式：总体名字-课名字
            safe_course = clean_filename(course_title)
            safe_section = clean_filename(section_title)
            filename = f"{safe_course}-{safe_section}.mp4"
        else:
            # 如果没有课程名称，只使用章节名称
            safe_title = clean_filename(section_title)
            filename = f"{safe_title}.mp4"
        
        output_path = output_dir / filename
        
        print(f"输出文件: {output_path}")
        print(f"\n开始下载...")
        
        # 根据格式选择下载方式
        if selected_option.format == "m3u8" or ".m3u8" in selected_option.play_url:
            success = self._download_m3u8_video(
                selected_option.play_url,
                str(output_path),
                progress_callback
            )
        else:
            success = self._download_mp4_video(
                selected_option.play_url,
                str(output_path),
                progress_callback
            )
        
        if success:
            print(f"✓ 下载完成: {output_path}")
            return str(output_path)
        else:
            print("✗ 下载失败")
            return None


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="知乎视频下载器 - 支持从 Chrome 读取 cookies 进行鉴权"
    )
    parser.add_argument(
        "url",
        help="知乎视频页面 URL 或视频 ID"
    )
    parser.add_argument(
        "-o", "--output",
        default=".",
        help="输出目录 (默认为当前目录)"
    )
    parser.add_argument(
        "-q", "--quality",
        default="hd",
        choices=["uhd", "fhd", "hd", "sd", "ld"],
        help="视频清晰度 (默认: hd)"
    )
    parser.add_argument(
        "-c", "--cookies",
        help="cookies 文件路径 (JSON 格式)，如果指定则优先使用"
    )
    parser.add_argument(
        "--no-cookies",
        action="store_true",
        help="不使用任何 cookies (仅能下载免费公开视频)"
    )
    
    args = parser.parse_args()
    
    # 创建下载器
    if args.no_cookies:
        downloader = ZhihuVideoDownloader(use_chrome_cookies=False)
    elif args.cookies:
        downloader = ZhihuVideoDownloader(use_chrome_cookies=False, cookie_file=args.cookies)
    else:
        downloader = ZhihuVideoDownloader(use_chrome_cookies=True)
    
    # 下载视频
    def progress_callback(progress):
        # 使用换行输出，便于 Go 程序按行解析进度
        print(f"下载进度: {progress:.1f}%", flush=True)
    
    result = downloader.download_video(
        args.url,
        output_dir=args.output,
        quality=args.quality,
        progress_callback=progress_callback
    )
    
    if result:
        print(f"\n\n✓ 视频已保存到: {result}")
        return 0
    else:
        print("\n\n✗ 下载失败")
        return 1


if __name__ == "__main__":
    exit(main())
