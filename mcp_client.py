#!/usr/bin/env python3
"""
知乎视频下载器 - MCP 客户端
用于与知乎视频下载器 MCP 服务通信
"""

import requests
import json
import time
from typing import Dict, Optional, Literal

class ZhihuDownloaderClient:
    """MCP 客户端"""
    
    def __init__(self, base_url: str = "http://127.0.0.1:5125"):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
    
    def download_video(self, url: str, output_path: Optional[str] = None) -> Dict:
        """
        下载知乎视频
        
        Args:
            url: 视频 URL
            output_path: 输出目录（可选）
        
        Returns:
            任务信息，包含 task_id
        """
        payload = {
            "name": "download_video",
            "input": {
                "url": url
            }
        }
        
        if output_path:
            payload["input"]["output_path"] = output_path
        
        response = self.session.post(
            f"{self.base_url}/mcp/call_tool",
            json=payload
        )
        response.raise_for_status()
        return response.json()["result"]
    
    def transcribe_video(self, video_path: str, language: str = "zh") -> Dict:
        """
        转录视频
        
        Args:
            video_path: 视频文件路径
            language: 语言代码（默认中文）
        
        Returns:
            任务信息，包含 task_id
        """
        payload = {
            "name": "transcribe_video",
            "input": {
                "video_path": video_path,
                "language": language
            }
        }
        
        response = self.session.post(
            f"{self.base_url}/mcp/call_tool",
            json=payload
        )
        response.raise_for_status()
        return response.json()["result"]
    
    def get_progress(self, task_id: str, task_type: Literal["download", "transcribe"]) -> Dict:
        """
        获取任务进度
        
        Args:
            task_id: 任务 ID
            task_type: 任务类型 (download 或 transcribe)
        
        Returns:
            任务进度信息
        """
        payload = {
            "name": "get_progress",
            "input": {
                "task_id": task_id,
                "task_type": task_type
            }
        }
        
        response = self.session.post(
            f"{self.base_url}/mcp/call_tool",
            json=payload
        )
        response.raise_for_status()
        return response.json()["result"]
    
    def wait_download(self, task_id: str, check_interval: int = 5) -> Dict:
        """
        等待下载完成
        
        Args:
            task_id: 下载任务 ID
            check_interval: 检查间隔（秒）
        
        Returns:
            最终的任务信息
        """
        while True:
            progress = self.get_progress(task_id, "download")
            
            status = progress.get("status")
            percentage = progress.get("percentage", 0)
            
            print(f"下载进度: {percentage}% ({status})")
            
            if status == "completed":
                print(f"✓ 下载完成: {progress.get('file_path')}")
                return progress
            elif status == "failed":
                print(f"✗ 下载失败: {progress.get('error')}")
                return progress
            
            time.sleep(check_interval)
    
    def wait_transcribe(self, task_id: str, check_interval: int = 10) -> Dict:
        """
        等待转录完成
        
        Args:
            task_id: 转录任务 ID
            check_interval: 检查间隔（秒）
        
        Returns:
            最终的任务信息
        """
        while True:
            progress = self.get_progress(task_id, "transcribe")
            
            status = progress.get("status")
            percentage = progress.get("percentage", 0)
            stage = progress.get("stage", "")
            
            print(f"转录进度: {percentage}% ({status}) - {stage}")
            
            if status == "completed":
                print(f"✓ 转录完成: {progress.get('txt_path')}")
                return progress
            elif status == "failed":
                print(f"✗ 转录失败: {progress.get('error')}")
                return progress
            
            time.sleep(check_interval)
    
    def download_and_transcribe(self, url: str, output_path: Optional[str] = None, language: str = "zh"):
        """
        完整工作流：下载视频并转录
        
        Args:
            url: 视频 URL
            output_path: 输出目录（可选）
            language: 转录语言（默认中文）
        """
        print(f"🎬 开始下载视频: {url}")
        print()
        
        # 下载
        download_result = self.download_video(url, output_path)
        download_task_id = download_result["task_id"]
        print(f"下载任务 ID: {download_task_id}")
        print()
        
        download_info = self.wait_download(download_task_id)
        
        if download_info["status"] != "completed":
            return
        
        video_path = download_info["file_path"]
        
        print()
        print(f"📝 开始转录视频: {video_path}")
        print()
        
        # 转录
        transcribe_result = self.transcribe_video(video_path, language)
        transcribe_task_id = transcribe_result["task_id"]
        print(f"转录任务 ID: {transcribe_task_id}")
        print()
        
        transcribe_info = self.wait_transcribe(transcribe_task_id)
        
        if transcribe_info["status"] == "completed":
            print()
            print("🎉 全部完成!")
            print(f"视频: {video_path}")
            print(f"音频: {transcribe_info.get('mp3_path')}")
            print(f"文本: {transcribe_info.get('txt_path')}")


def main():
    """示例用法"""
    import sys
    
    client = ZhihuDownloaderClient()
    
    if len(sys.argv) < 2:
        print("使用方法:")
        print("  python mcp_client.py download <url> [output_path]")
        print("  python mcp_client.py transcribe <video_path> [language]")
        print("  python mcp_client.py full <url> [language]")
        print("  python mcp_client.py progress <task_id> <download|transcribe>")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "download":
        url = sys.argv[2]
        output_path = sys.argv[3] if len(sys.argv) > 3 else None
        
        result = client.download_video(url, output_path)
        task_id = result["task_id"]
        
        print(f"下载任务已启动: {task_id}")
        client.wait_download(task_id)
    
    elif command == "transcribe":
        video_path = sys.argv[2]
        language = sys.argv[3] if len(sys.argv) > 3 else "zh"
        
        result = client.transcribe_video(video_path, language)
        task_id = result["task_id"]
        
        print(f"转录任务已启动: {task_id}")
        client.wait_transcribe(task_id)
    
    elif command == "full":
        url = sys.argv[2]
        language = sys.argv[3] if len(sys.argv) > 3 else "zh"
        
        client.download_and_transcribe(url, language=language)
    
    elif command == "progress":
        task_id = sys.argv[2]
        task_type = sys.argv[3]
        
        progress = client.get_progress(task_id, task_type)
        print(json.dumps(progress, indent=2, ensure_ascii=False))
    
    else:
        print(f"未知命令: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()

