#!/usr/bin/env python3
"""
知乎视频下载器 - FastAPI 后端服务

为 Electron 前端提供 API 接口
"""

import os
import uuid
import asyncio
from typing import Optional, Dict, List
from pathlib import Path
from dataclasses import dataclass, asdict

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# 导入下载器核心功能
from zhihu_downloader import ZhihuVideoDownloader, VideoInfo, DownloadOption

app = FastAPI(title="知乎视频下载器 API", version="1.0.0")

# 允许跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局下载器实例
downloader: Optional[ZhihuVideoDownloader] = None

# 下载任务存储
downloads: Dict[str, dict] = {}


class ParseRequest(BaseModel):
    url: str


class ParseResponse(BaseModel):
    video_id: str
    title: str
    duration: int
    options: List[dict]


class DownloadRequest(BaseModel):
    url: str
    quality: str = "hd"
    output_path: Optional[str] = None


class DownloadResponse(BaseModel):
    download_id: str


class ProgressResponse(BaseModel):
    status: str
    percentage: int
    file_name: Optional[str] = None
    file_path: Optional[str] = None
    error: Optional[str] = None


class CookiesRequest(BaseModel):
    cookies: List[dict]


@app.on_event("startup")
async def startup():
    """启动时初始化下载器"""
    global downloader
    downloader = ZhihuVideoDownloader(use_chrome_cookies=True)


@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "authenticated": downloader is not None}


@app.post("/api/parse", response_model=ParseResponse)
async def parse_video(request: ParseRequest):
    """解析视频页面，获取视频信息和下载选项"""
    if not downloader:
        raise HTTPException(status_code=500, detail="下载器未初始化")
    
    try:
        # 提取视频 ID
        video_id = None
        page_info = None
        
        if not request.url.startswith("http"):
            video_id = request.url
        else:
            video_id = downloader._extract_video_id_from_url(request.url)
        
        if not video_id:
            page_info = downloader._get_video_info_from_page(request.url)
            if page_info:
                video_id = page_info.get("video_id")
        
        # 如果页面解析时已经获取到了 playlist，直接使用
        if page_info and page_info.get("source") == "page_mp4" and page_info.get("playlist"):
            from zhihu_downloader import VideoInfo
            video_info = VideoInfo(
                video_id="direct_mp4",
                title=page_info.get("title", "zhihu_video"),
                duration=0,
                playlist=page_info.get("playlist", {})
            )
        elif not video_id:
            raise HTTPException(status_code=400, detail="无法解析视频 ID")
        else:
            # 获取视频信息
            video_title = page_info.get("title", "") if page_info else ""
            video_info = downloader.get_video_info(video_id, video_title)
            
            if not video_info:
                raise HTTPException(status_code=400, detail="无法获取视频信息")
        
        # 获取下载选项
        options = downloader.get_download_options(video_info)
        
        return ParseResponse(
            video_id=video_id,
            title=video_info.title,
            duration=video_info.duration,
            options=[{
                "quality": opt.quality,
                "width": opt.width,
                "height": opt.height,
                "format": opt.format,
                "size": f"{opt.width}x{opt.height}"
            } for opt in options]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/download", response_model=DownloadResponse)
async def start_download(request: DownloadRequest, background_tasks: BackgroundTasks):
    """开始下载视频"""
    if not downloader:
        raise HTTPException(status_code=500, detail="下载器未初始化")
    
    download_id = str(uuid.uuid4())
    
    # 初始化下载状态
    downloads[download_id] = {
        "status": "Starting",
        "percentage": 0,
        "file_name": None,
        "file_path": None,
        "error": None
    }
    
    # 在后台执行下载
    background_tasks.add_task(
        do_download,
        download_id,
        request.url,
        request.quality,
        request.output_path
    )
    
    return DownloadResponse(download_id=download_id)


async def do_download(download_id: str, url: str, quality: str, output_path: Optional[str]):
    """执行下载任务"""
    try:
        print(f"[下载任务 {download_id}] 开始下载: {url}, 清晰度: {quality}")
        downloads[download_id]["status"] = "Downloading"
        downloads[download_id]["percentage"] = 0
        
        # 默认下载目录
        if not output_path:
            output_path = str(Path.home() / "Downloads")
        
        def progress_callback(progress: float):
            progress_int = int(progress)
            downloads[download_id]["percentage"] = progress_int
            print(f"[下载任务 {download_id}] 进度更新: {progress_int}%")
        
        # 执行下载
        print(f"[下载任务 {download_id}] 调用 download_video...")
        result = downloader.download_video(
            url,
            output_dir=output_path,
            quality=quality,
            progress_callback=progress_callback
        )
        
        print(f"[下载任务 {download_id}] 下载完成，结果: {result}")
        if result:
            downloads[download_id]["status"] = "Completed"
            downloads[download_id]["percentage"] = 100
            downloads[download_id]["file_path"] = result
            downloads[download_id]["file_name"] = Path(result).name
            print(f"[下载任务 {download_id}] 成功完成")
        else:
            downloads[download_id]["status"] = "Failed"
            downloads[download_id]["error"] = "下载失败"
            print(f"[下载任务 {download_id}] 下载失败")
            
    except Exception as e:
        print(f"[下载任务 {download_id}] 发生异常: {e}")
        import traceback
        traceback.print_exc()
        downloads[download_id]["status"] = "Failed"
        downloads[download_id]["error"] = str(e)


@app.get("/api/progress/{download_id}", response_model=ProgressResponse)
async def get_progress(download_id: str):
    """获取下载进度"""
    if download_id not in downloads:
        raise HTTPException(status_code=404, detail="下载任务不存在")
    
    return ProgressResponse(**downloads[download_id])


@app.post("/api/cookies")
async def set_cookies(request: CookiesRequest):
    """设置 cookies"""
    global downloader
    
    try:
        # 重新创建下载器并设置 cookies
        downloader = ZhihuVideoDownloader(use_chrome_cookies=False)
        
        for cookie in request.cookies:
            downloader.session.cookies.set(
                cookie.get('name'),
                cookie.get('value'),
                domain=cookie.get('domain', '.zhihu.com')
            )
        
        return {"status": "ok", "count": len(request.cookies)}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/cookies/check")
async def check_cookies():
    """检查 cookies 状态"""
    if not downloader:
        return {"authenticated": False, "cookies": []}
    
    cookie_names = [c.name for c in downloader.session.cookies]
    has_auth = "z_c0" in cookie_names
    
    return {
        "authenticated": has_auth,
        "cookies": cookie_names
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=5124)

