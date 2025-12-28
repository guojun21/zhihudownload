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

// 任务管理
type DownloadTask struct {
	ID          string    `json:"id"`
	Status      string    `json:"status"` // pending, downloading, completed, failed
	Percentage  int       `json:"percentage"`
	Speed       string    `json:"speed,omitempty"`
	ElapsedTime int       `json:"elapsed_time"`
	FilePath    string    `json:"file_path,omitempty"`
	Error       string    `json:"error,omitempty"`
	VideoURL    string    `json:"video_url"`
	Quality     string    `json:"quality"`
	StartTime   time.Time `json:"-"`
}

type TranscribeTask struct {
	ID          string    `json:"id"`
	Status      string    `json:"status"` // extracting_audio, transcribing, completed, failed
	Percentage  int       `json:"percentage"`
	Stage       string    `json:"stage,omitempty"`
	ElapsedTime int       `json:"elapsed_time"`
	MP3Path     string    `json:"mp3_path,omitempty"`
	TXTPath     string    `json:"txt_path,omitempty"`
	Error       string    `json:"error,omitempty"`
	VideoPath   string    `json:"video_path"`
	StartTime   time.Time `json:"-"`
}

var (
	downloadTasks = make(map[string]*DownloadTask)
	transcribeTasks = make(map[string]*TranscribeTask)
	mu             = &sync.RWMutex{}
)

func main() {
	gin.SetMode(gin.ReleaseMode)
	router := gin.Default()

	// CORS
	router.Use(func(c *gin.Context) {
		c.Header("Access-Control-Allow-Origin", "*")
		c.Header("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS")
		c.Header("Access-Control-Allow-Headers", "Content-Type")
		if c.Request.Method == "OPTIONS" {
			c.AbortWithStatus(204)
			return
		}
		c.Next()
	})

	// ============ MCP 服务 API ============

	// 列出可用的工具/功能
	router.GET("/mcp/tools", func(c *gin.Context) {
		tools := []map[string]interface{}{
			{
				"name": "download_video",
				"description": "下载知乎视频为 MP4 格式（默认最高清晰度）",
				"inputSchema": map[string]interface{}{
					"type": "object",
					"properties": map[string]interface{}{
						"url": map[string]interface{}{
							"type": "string",
							"description": "知乎视频 URL",
						},
						"output_path": map[string]interface{}{
							"type": "string",
							"description": "输出路径（默认 ~/Downloads）",
						},
					},
					"required": []string{"url"},
				},
			},
			{
				"name": "transcribe_video",
				"description": "将视频转录为文本（包括音频提取和 Whisper 转录）",
				"inputSchema": map[string]interface{}{
					"type": "object",
					"properties": map[string]interface{}{
						"video_path": map[string]interface{}{
							"type": "string",
							"description": "MP4 视频文件路径",
						},
						"language": map[string]interface{}{
							"type": "string",
							"description": "语言代码（默认 zh 中文）",
						},
					},
					"required": []string{"video_path"},
				},
			},
			{
				"name": "get_progress",
				"description": "获取下载或转录任务的进度",
				"inputSchema": map[string]interface{}{
					"type": "object",
					"properties": map[string]interface{}{
						"task_id": map[string]interface{}{
							"type": "string",
							"description": "任务 ID",
						},
						"task_type": map[string]interface{}{
							"type": "string",
							"enum": []string{"download", "transcribe"},
							"description": "任务类型",
						},
					},
					"required": []string{"task_id", "task_type"},
				},
			},
		}
		c.JSON(200, gin.H{"tools": tools})
	})

	// 调用工具
	router.POST("/mcp/call_tool", func(c *gin.Context) {
		var req struct {
			Name   string                 `json:"name"`
			Input  map[string]interface{} `json:"input"`
		}

		if err := c.BindJSON(&req); err != nil {
			c.JSON(400, gin.H{"error": err.Error()})
			return
		}

		var response interface{}
		var err error

		switch req.Name {
		case "download_video":
			response, err = handleDownloadVideo(req.Input)
		case "transcribe_video":
			response, err = handleTranscribeVideo(req.Input)
		case "get_progress":
			response, err = handleGetProgress(req.Input)
		default:
			c.JSON(404, gin.H{"error": "未知的工具"})
			return
		}

		if err != nil {
			c.JSON(400, gin.H{"error": err.Error()})
			return
		}

		c.JSON(200, gin.H{"result": response})
	})

	// ============ 健康检查 ============
	router.GET("/health", func(c *gin.Context) {
		c.JSON(200, gin.H{"status": "ok", "service": "zhihu-downloader-mcp"})
	})

	fmt.Println("✓ MCP 服务启动在 http://127.0.0.1:5125")
	fmt.Println("  可用端点:")
	fmt.Println("    GET  /mcp/tools           - 列出所有工具")
	fmt.Println("    POST /mcp/call_tool       - 调用工具")
	fmt.Println("    GET  /health             - 健康检查")

	router.Run("127.0.0.1:5125")
}

// ============ 工具处理函数 ============

func handleDownloadVideo(input map[string]interface{}) (interface{}, error) {
	url, ok := input["url"].(string)
	if !ok || url == "" {
		return nil, fmt.Errorf("URL 必填")
	}

	outputPath, _ := input["output_path"].(string)
	if outputPath == "" {
		outputPath = filepath.Join(os.Getenv("HOME"), "Downloads")
	}

	taskID := uuid.New().String()
	task := &DownloadTask{
		ID:        taskID,
		Status:    "pending",
		VideoURL:  url,
		Quality:   "hd", // 默认最高清晰度
		StartTime: time.Now(),
	}

	mu.Lock()
	downloadTasks[taskID] = task
	mu.Unlock()

	// 在后台执行下载
	go downloadVideoWorker(taskID, url, outputPath)

	return gin.H{
		"task_id": taskID,
		"status": "已启动下载任务",
	}, nil
}

func handleTranscribeVideo(input map[string]interface{}) (interface{}, error) {
	videoPath, ok := input["video_path"].(string)
	if !ok || videoPath == "" {
		return nil, fmt.Errorf("video_path 必填")
	}

	language, _ := input["language"].(string)
	if language == "" {
		language = "zh"
	}

	if _, err := os.Stat(videoPath); err != nil {
		return nil, fmt.Errorf("视频文件不存在: %v", err)
	}

	taskID := uuid.New().String()
	task := &TranscribeTask{
		ID:        taskID,
		Status:    "extracting_audio",
		VideoPath: videoPath,
		StartTime: time.Now(),
	}

	mu.Lock()
	transcribeTasks[taskID] = task
	mu.Unlock()

	// 在后台执行转录
	go transcribeVideoWorker(taskID, videoPath, language)

	return gin.H{
		"task_id": taskID,
		"status": "已启动转录任务",
	}, nil
}

func handleGetProgress(input map[string]interface{}) (interface{}, error) {
	taskID, ok := input["task_id"].(string)
	if !ok || taskID == "" {
		return nil, fmt.Errorf("task_id 必填")
	}

	taskType, ok := input["task_type"].(string)
	if !ok || taskType == "" {
		return nil, fmt.Errorf("task_type 必填 (download 或 transcribe)")
	}

	mu.RLock()
	defer mu.RUnlock()

	if taskType == "download" {
		task, exists := downloadTasks[taskID]
		if !exists {
			return nil, fmt.Errorf("下载任务不存在")
		}
		return task, nil
	} else if taskType == "transcribe" {
		task, exists := transcribeTasks[taskID]
		if !exists {
			return nil, fmt.Errorf("转录任务不存在")
		}
		return task, nil
	}

	return nil, fmt.Errorf("未知的任务类型")
}

// ============ 工作函数 ============

func downloadVideoWorker(taskID, url, outputPath string) {
	mu.Lock()
	task := downloadTasks[taskID]
	task.Status = "downloading"
	task.Percentage = 0
	mu.Unlock()

	os.MkdirAll(outputPath, 0755)
	outputFile := filepath.Join(outputPath, fmt.Sprintf("video_%s.mp4", taskID[:8]))

	// 调用 ffmpeg 下载
	cmd := exec.Command("ffmpeg", "-y", "-i", url, "-c", "copy", "-progress", "pipe:1", outputFile)
	stdout, _ := cmd.StdoutPipe()

	go func() {
		scanner := bufio.NewScanner(stdout)
		for scanner.Scan() {
			line := scanner.Text()
			if strings.Contains(line, "progress=") {
				mu.Lock()
				task.Percentage = min(99, task.Percentage+1)
				task.ElapsedTime = int(time.Since(task.StartTime).Seconds())
				mu.Unlock()
			}
		}
	}()

	err := cmd.Run()

	mu.Lock()
	if err != nil {
		task.Status = "failed"
		task.Error = err.Error()
	} else {
		if info, err := os.Stat(outputFile); err == nil && info.Size() > 0 {
			task.Status = "completed"
			task.Percentage = 100
			task.FilePath = outputFile
			fmt.Printf("[%s] 下载完成: %s\n", taskID, outputFile)
		} else {
			task.Status = "failed"
			task.Error = "文件为空或不存在"
		}
	}
	mu.Unlock()
}

func transcribeVideoWorker(taskID, videoPath, language string) {
	mu.Lock()
	task := transcribeTasks[taskID]
	mu.Unlock()

	// 步骤1: 提取音频
	mu.Lock()
	task.Status = "extracting_audio"
	task.Stage = "正在提取音频..."
	task.Percentage = 10
	mu.Unlock()

	mp3Path := strings.TrimSuffix(videoPath, filepath.Ext(videoPath)) + ".mp3"

	cmd := exec.Command("ffmpeg", "-y", "-i", videoPath, "-q:a", "9", mp3Path)
	output, err := cmd.CombinedOutput()

	if err != nil {
		mu.Lock()
		task.Status = "failed"
		task.Error = fmt.Sprintf("音频提取失败: %v", err)
		mu.Unlock()
		return
	}

	if _, err := os.Stat(mp3Path); err != nil {
		mu.Lock()
		task.Status = "failed"
		task.Error = "MP3 文件未创建"
		mu.Unlock()
		return
	}

	fmt.Printf("[%s] 音频提取完成\n", taskID)

	// 步骤2: 转录
	mu.Lock()
	task.Status = "transcribing"
	task.Stage = "正在转录..."
	task.Percentage = 50
	mu.Unlock()

	outputDir := filepath.Dir(videoPath)
	whisperCmd := exec.Command("bash", "-c",
		fmt.Sprintf("export PATH=/opt/homebrew/bin:$PATH && /opt/homebrew/bin/whisper %q --output_format txt --output_dir %q --language %s --model base 2>&1",
			mp3Path, outputDir, language))

	output, err = whisperCmd.CombinedOutput()

	if err != nil {
		mu.Lock()
		task.Status = "failed"
		task.Error = fmt.Sprintf("转录失败: %v\n%s", err, string(output))
		mu.Unlock()
		return
	}

	txtPath := strings.TrimSuffix(mp3Path, filepath.Ext(mp3Path)) + ".txt"

	// 步骤3: 完成
	mu.Lock()
	task.Status = "completed"
	task.Percentage = 100
	task.MP3Path = mp3Path
	task.TXTPath = txtPath
	task.ElapsedTime = int(time.Since(task.StartTime).Seconds())
	mu.Unlock()

	fmt.Printf("[%s] 转录完成: %s\n", taskID, txtPath)
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

