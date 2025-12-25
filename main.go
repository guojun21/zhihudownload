package main

import (
	"bufio"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
)

// DownloadTask 下载任务状态
type DownloadTask struct {
	ID          string    `json:"download_id"`
	Status      string    `json:"status"`
	Percentage  int       `json:"percentage"`
	Speed       *string   `json:"speed"`
	ElapsedTime int       `json:"elapsed_time"`
	FilePath    *string   `json:"file_path"`
	FileName    *string   `json:"file_name"`
	Error       *string   `json:"error"`
	StartTime   time.Time `json:"-"`
}

// TranscribeTask 转录任务状态
type TranscribeTask struct {
	ID          string    `json:"task_id"`
	Status      string    `json:"status"`
	Percentage  int       `json:"percentage"`
	Stage       *string   `json:"stage"`
	ElapsedTime int       `json:"elapsed_time"`
	VideoPath   string    `json:"-"`
	MP3Path     *string   `json:"mp3_path"`
	TxtPath     *string   `json:"txt_path"`
	Error       *string   `json:"error"`
	StartTime   time.Time `json:"-"`
}

var (
	tasks       = make(map[string]*DownloadTask)
	transcribes = make(map[string]*TranscribeTask)
	mu          = &sync.RWMutex{}
)

func main() {
	gin.SetMode(gin.ReleaseMode)
	router := gin.Default()

	// 跨域支持
	router.Use(func(c *gin.Context) {
		c.Header("Access-Control-Allow-Origin", "*")
		c.Header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
		c.Header("Access-Control-Allow-Headers", "Content-Type, Authorization")
		if c.Request.Method == "OPTIONS" {
			c.AbortWithStatus(204)
			return
		}
		c.Next()
	})

	// API 路由
	router.GET("/api/health", func(c *gin.Context) {
		c.JSON(200, gin.H{
			"status":        "ok",
			"authenticated": true,
		})
	})

	router.POST("/api/download", func(c *gin.Context) {
		var req struct {
			URL        string `json:"url" binding:"required"`
			Quality    string `json:"quality"`
			OutputPath string `json:"output_path"`
		}

		if err := c.BindJSON(&req); err != nil {
			c.JSON(400, gin.H{"error": err.Error()})
			return
		}

		if req.Quality == "" {
			req.Quality = "hd"
		}

		taskID := uuid.New().String()
		task := &DownloadTask{
			ID:        taskID,
			Status:    "Starting",
			StartTime: time.Now(),
		}

		mu.Lock()
		tasks[taskID] = task
		mu.Unlock()

		// 在 goroutine 中执行下载
		go downloadVideo(taskID, req.URL, req.Quality, req.OutputPath)

		c.JSON(200, gin.H{"download_id": taskID})
	})

	router.GET("/api/progress/:download_id", func(c *gin.Context) {
		downloadID := c.Param("download_id")

		mu.RLock()
		task, exists := tasks[downloadID]
		mu.RUnlock()

		if !exists {
			c.JSON(404, gin.H{"error": "任务不存在"})
			return
		}

		c.JSON(200, task)
	})

	router.POST("/api/download/:download_id/cancel", func(c *gin.Context) {
		downloadID := c.Param("download_id")

		mu.Lock()
		if task, exists := tasks[downloadID]; exists {
			if task.Status == "Downloading" {
				task.Status = "Cancelled"
				errMsg := "用户取消"
				task.Error = &errMsg
			}
		}
		mu.Unlock()

		c.JSON(200, gin.H{"status": "cancelled"})
	})

	// 转录相关路由
	router.POST("/api/transcribe", func(c *gin.Context) {
		var req struct {
			VideoPath string `json:"video_path" binding:"required"`
			Language  string `json:"language"`
		}

		if err := c.BindJSON(&req); err != nil {
			c.JSON(400, gin.H{"error": err.Error()})
			return
		}

		if req.Language == "" {
			req.Language = "zh"
		}

		taskID := uuid.New().String()
		task := &TranscribeTask{
			ID:        taskID,
			Status:    "pending",
			VideoPath: req.VideoPath,
			StartTime: time.Now(),
		}

		mu.Lock()
		transcribes[taskID] = task
		mu.Unlock()

		// 在 goroutine 中执行转录
		go transcribeVideo(taskID, req.VideoPath, req.Language)

		c.JSON(200, gin.H{"task_id": taskID})
	})

	router.GET("/api/transcribe/:task_id", func(c *gin.Context) {
		taskID := c.Param("task_id")

		mu.RLock()
		task, exists := transcribes[taskID]
		mu.RUnlock()

		if !exists {
			c.JSON(404, gin.H{"error": "任务不存在"})
			return
		}

		c.JSON(200, task)
	})

	fmt.Println("✓ 服务启动在 http://127.0.0.1:5124 (Go 网关 + ffmpeg + Whisper)")
	router.Run("127.0.0.1:5124")
}

// downloadVideo 下载视频（调用 ffmpeg）
func downloadVideo(taskID, url, quality, outputPath string) {
	mu.Lock()
	task := tasks[taskID]
	task.Status = "Downloading"
	mu.Unlock()

	if outputPath == "" {
		outputPath = filepath.Join(os.Getenv("HOME"), "Downloads")
	}

	os.MkdirAll(outputPath, 0755)
	outputFile := filepath.Join(outputPath, fmt.Sprintf("video_%s.mp4", taskID[:8]))

	// 启动 ffmpeg 下载
	cmd := exec.Command("ffmpeg", "-y", "-i", url, "-c", "copy", "-progress", "pipe:1", outputFile)
	
	stdout, _ := cmd.StdoutPipe()
	
	go func() {
		scanner := bufio.NewScanner(stdout)
		for scanner.Scan() {
			line := scanner.Text()
			if strings.Contains(line, "progress=") {
				mu.Lock()
				if task.Status == "Downloading" {
					task.Percentage = min(99, task.Percentage+1)
					task.ElapsedTime = int(time.Since(task.StartTime).Seconds())
					if task.ElapsedTime > 0 && task.Percentage > 0 {
						speedKb := float64(task.Percentage) / float64(task.ElapsedTime) / 100
						var speedStr string
						if speedKb > 1024 {
							speedStr = fmt.Sprintf("%.1f MB/s", speedKb/1024)
						} else {
							speedStr = fmt.Sprintf("%.0f KB/s", speedKb)
						}
						task.Speed = &speedStr
					}
				}
				mu.Unlock()
			}
		}
	}()

	err := cmd.Run()
	
	mu.Lock()
	defer mu.Unlock()

	if err != nil {
		task.Status = "Failed"
		errMsg := fmt.Sprintf("下载失败: %v", err)
		task.Error = &errMsg
	} else {
		if info, err := os.Stat(outputFile); err == nil && info.Size() > 0 {
			task.Status = "Completed"
			task.Percentage = 100
			task.FilePath = &outputFile
			fileName := filepath.Base(outputFile)
			task.FileName = &fileName
			fmt.Printf("[%s] 下载完成: %s (%.1f MB)\n", taskID, outputFile, float64(info.Size())/1024/1024)
		} else {
			task.Status = "Failed"
			errMsg := "文件为空或不存在"
			task.Error = &errMsg
		}
	}
}

// transcribeVideo 转录视频（使用 ffmpeg + whisper）
func transcribeVideo(taskID, videoPath, language string) {
	mu.Lock()
	task := transcribes[taskID]
	mu.Unlock()

	// 步骤1: 提取音频为 MP3
	mu.Lock()
	task.Status = "extracting_audio"
	stage := "正在提取音频..."
	task.Stage = &stage
	task.Percentage = 10
	mu.Unlock()

	mp3Path := strings.TrimSuffix(videoPath, filepath.Ext(videoPath)) + ".mp3"

	// 用 ffmpeg 从视频提取音频
	cmd := exec.Command("ffmpeg", "-y", "-i", videoPath, "-q:a", "9", "-n", mp3Path)
	if err := cmd.Run(); err != nil {
		mu.Lock()
		task.Status = "failed"
		errMsg := fmt.Sprintf("提取音频失败: %v", err)
		task.Error = &errMsg
		mu.Unlock()
		fmt.Printf("[%s] 错误: %s\n", taskID, errMsg)
		return
	}

	fmt.Printf("[%s] 音频提取完成: %s\n", taskID, mp3Path)

	// 步骤2: 用 whisper 转录
	mu.Lock()
	task.Status = "transcribing"
	stage = "正在转录（Whisper）..."
	task.Stage = &stage
	task.Percentage = 50
	mu.Unlock()

	// 输出目录
	outputDir := filepath.Dir(videoPath)
	
	// 调用 whisper CLI
	whisperCmd := exec.Command("whisper", mp3Path, 
		"--output_format", "txt", 
		"--output_dir", outputDir, 
		"--language", language,
		"--model", "base")

	output, err := whisperCmd.CombinedOutput()
	
	if err != nil {
		mu.Lock()
		task.Status = "failed"
		errMsg := fmt.Sprintf("Whisper 转录失败: %v\n输出: %s", err, string(output))
		task.Error = &errMsg
		mu.Unlock()
		fmt.Printf("[%s] 错误: %s\n", taskID, errMsg)
		return
	}

	// 查找生成的 txt 文件
	txtPath := strings.TrimSuffix(mp3Path, filepath.Ext(mp3Path)) + ".txt"

	// 步骤3: 完成
	mu.Lock()
	task.Status = "completed"
	task.Percentage = 100
	task.MP3Path = &mp3Path
	task.TxtPath = &txtPath
	task.ElapsedTime = int(time.Since(task.StartTime).Seconds())
	mu.Unlock()

	fmt.Printf("[%s] 转录完成！\n  MP3: %s\n  TXT: %s\n  耗时: %ds\n", taskID, mp3Path, txtPath, task.ElapsedTime)
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
