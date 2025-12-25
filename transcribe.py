#!/usr/bin/env python3
"""
视频转录模块

将 MP4 视频转换为 MP3 音频，然后使用 Whisper 模型转录为文字。
使用 Buzz 下载的模型，避免重复下载。

依赖:
    - whisper (openai-whisper)
    - ffmpeg (系统命令行工具)
"""

import os
import subprocess
import shutil
from pathlib import Path
from typing import Optional, Callable
from dataclasses import dataclass

# Whisper 模型路径 (Buzz 下载的模型)
BUZZ_MODEL_PATH = Path.home() / "Library/Caches/Buzz/models/whisper"

@dataclass
class TranscribeResult:
    """转录结果"""
    mp3_path: str
    txt_path: str
    text: str
    duration: float  # 音频时长（秒）


class VideoTranscriber:
    """视频转录器"""
    
    def __init__(self, model_size: str = "medium"):
        """
        初始化转录器
        
        Args:
            model_size: 模型大小，支持 "small" 或 "medium"
        """
        self.model_size = model_size
        self.model = None
        self._check_dependencies()
    
    def _check_dependencies(self):
        """检查依赖"""
        # 检查 ffmpeg
        if not shutil.which("ffmpeg"):
            raise RuntimeError("未找到 ffmpeg，请先安装: brew install ffmpeg")
        
        # 检查模型文件
        model_path = BUZZ_MODEL_PATH / f"{self.model_size}.pt"
        if not model_path.exists():
            raise RuntimeError(
                f"未找到 Whisper {self.model_size} 模型\n"
                f"请先在 Buzz 应用中下载 {self.model_size} 模型\n"
                f"期望路径: {model_path}"
            )
    
    def _load_model(self, progress_callback: Optional[Callable[[str, int], None]] = None):
        """延迟加载模型"""
        if self.model is not None:
            return
        
        if progress_callback:
            progress_callback("loading_model", 0)
        
        try:
            import whisper
        except ImportError:
            raise RuntimeError("请安装 whisper: pip install openai-whisper")
        
        # 设置模型下载目录为 Buzz 的缓存目录
        # 这样 whisper 会直接使用 Buzz 下载的模型
        os.environ["XDG_CACHE_HOME"] = str(BUZZ_MODEL_PATH.parent.parent)
        
        print(f"正在加载 Whisper {self.model_size} 模型...")
        
        # 直接从 Buzz 的模型路径加载
        model_path = BUZZ_MODEL_PATH / f"{self.model_size}.pt"
        self.model = whisper.load_model(self.model_size, download_root=str(BUZZ_MODEL_PATH))
        
        print(f"✓ 模型加载完成")
        
        if progress_callback:
            progress_callback("model_loaded", 5)
    
    def extract_audio(
        self, 
        video_path: str, 
        output_path: Optional[str] = None,
        progress_callback: Optional[Callable[[str, int], None]] = None
    ) -> str:
        """
        从视频中提取音频
        
        Args:
            video_path: 视频文件路径
            output_path: 输出音频路径（可选，默认与视频同目录同名）
            progress_callback: 进度回调 (stage, percentage)
            
        Returns:
            音频文件路径
        """
        video_path = Path(video_path)
        
        if not video_path.exists():
            raise FileNotFoundError(f"视频文件不存在: {video_path}")
        
        # 默认输出路径：与视频同目录同名
        if output_path is None:
            output_path = video_path.with_suffix(".mp3")
        else:
            output_path = Path(output_path)
        
        if progress_callback:
            progress_callback("extracting_audio", 10)
        
        print(f"正在提取音频: {video_path.name} -> {output_path.name}")
        
        # 使用 ffmpeg 提取音频
        cmd = [
            "ffmpeg",
            "-i", str(video_path),
            "-vn",  # 不要视频
            "-acodec", "libmp3lame",  # 使用 MP3 编码
            "-ab", "192k",  # 比特率
            "-ar", "16000",  # 采样率 (Whisper 推荐 16kHz)
            "-ac", "1",  # 单声道
            "-y",  # 覆盖已存在的文件
            str(output_path)
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            if progress_callback:
                progress_callback("audio_extracted", 20)
            
            print(f"✓ 音频提取完成: {output_path}")
            return str(output_path)
            
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"音频提取失败: {e.stderr}")
    
    def transcribe(
        self,
        audio_path: str,
        output_path: Optional[str] = None,
        language: str = "zh",
        progress_callback: Optional[Callable[[str, int], None]] = None
    ) -> TranscribeResult:
        """
        转录音频为文字
        
        Args:
            audio_path: 音频文件路径
            output_path: 输出文本路径（可选，默认与音频同目录同名）
            language: 语言代码，默认中文
            progress_callback: 进度回调 (stage, percentage)
            
        Returns:
            TranscribeResult 对象
        """
        audio_path = Path(audio_path)
        
        if not audio_path.exists():
            raise FileNotFoundError(f"音频文件不存在: {audio_path}")
        
        # 默认输出路径：与音频同目录同名
        if output_path is None:
            output_path = audio_path.with_suffix(".txt")
        else:
            output_path = Path(output_path)
        
        # 加载模型
        self._load_model(progress_callback)
        
        if progress_callback:
            progress_callback("transcribing", 25)
        
        print(f"正在转录音频: {audio_path.name}")
        print(f"语言: {language}")
        
        # 执行转录
        result = self.model.transcribe(
            str(audio_path),
            language=language,
            task="transcribe",
            verbose=False
        )
        
        if progress_callback:
            progress_callback("transcription_done", 90)
        
        # 提取文本
        text = result["text"].strip()
        
        # 保存到文件
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(text)
        
        if progress_callback:
            progress_callback("completed", 100)
        
        print(f"✓ 转录完成: {output_path}")
        print(f"  文字长度: {len(text)} 字符")
        
        # 获取音频时长
        duration = 0
        try:
            import whisper
            audio = whisper.load_audio(str(audio_path))
            duration = len(audio) / 16000  # 采样率 16kHz
        except:
            pass
        
        return TranscribeResult(
            mp3_path=str(audio_path),
            txt_path=str(output_path),
            text=text,
            duration=duration
        )
    
    def process_video(
        self,
        video_path: str,
        language: str = "zh",
        progress_callback: Optional[Callable[[str, int], None]] = None
    ) -> TranscribeResult:
        """
        处理视频：提取音频并转录
        
        Args:
            video_path: 视频文件路径
            language: 语言代码，默认中文
            progress_callback: 进度回调 (stage, percentage)
            
        Returns:
            TranscribeResult 对象
        """
        video_path = Path(video_path)
        
        if not video_path.exists():
            raise FileNotFoundError(f"视频文件不存在: {video_path}")
        
        # 输出文件与视频同目录
        mp3_path = video_path.with_suffix(".mp3")
        txt_path = video_path.with_suffix(".txt")
        
        # 提取音频
        self.extract_audio(str(video_path), str(mp3_path), progress_callback)
        
        # 转录
        result = self.transcribe(str(mp3_path), str(txt_path), language, progress_callback)
        
        return result


def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="视频转录工具 - 将 MP4 转换为 MP3 并使用 Whisper 转录为文字"
    )
    parser.add_argument(
        "video",
        help="视频文件路径"
    )
    parser.add_argument(
        "-m", "--model",
        default="medium",
        choices=["small", "medium"],
        help="Whisper 模型大小 (默认: medium)"
    )
    parser.add_argument(
        "-l", "--language",
        default="zh",
        help="语言代码 (默认: zh 中文)"
    )
    
    args = parser.parse_args()
    
    def progress_callback(stage: str, percentage: int):
        stages = {
            "loading_model": "加载模型",
            "model_loaded": "模型已加载",
            "extracting_audio": "提取音频",
            "audio_extracted": "音频已提取",
            "transcribing": "正在转录",
            "transcription_done": "转录完成",
            "completed": "处理完成"
        }
        stage_name = stages.get(stage, stage)
        print(f"\r[{percentage:3d}%] {stage_name}...", end="", flush=True)
        if percentage == 100:
            print()
    
    try:
        transcriber = VideoTranscriber(model_size=args.model)
        result = transcriber.process_video(
            args.video,
            language=args.language,
            progress_callback=progress_callback
        )
        
        print(f"\n处理完成!")
        print(f"  MP3: {result.mp3_path}")
        print(f"  TXT: {result.txt_path}")
        print(f"  时长: {result.duration:.1f} 秒")
        print(f"  文字: {result.text[:100]}..." if len(result.text) > 100 else f"  文字: {result.text}")
        
    except Exception as e:
        print(f"\n错误: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())


