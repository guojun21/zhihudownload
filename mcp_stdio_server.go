package main

import (
	"bufio"
	"database/sql"
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"sync"
	"time"

	_ "github.com/mattn/go-sqlite3"
)

// MCP JSON-RPC 消息结构
type JSONRPCRequest struct {
	JSONRPC string          `json:"jsonrpc"`
	ID      interface{}     `json:"id"`
	Method  string          `json:"method"`
	Params  json.RawMessage `json:"params,omitempty"`
}

type JSONRPCResponse struct {
	JSONRPC string      `json:"jsonrpc"`
	ID      interface{} `json:"id"`
	Result  interface{} `json:"result,omitempty"`
	Error   *RPCError   `json:"error,omitempty"`
}

type RPCError struct {
	Code    int    `json:"code"`
	Message string `json:"message"`
}

// 任务结构
type DownloadTask struct {
	ID          string `json:"id"`
	Status      string `json:"status"`
	Percentage  int    `json:"percentage"`
	Speed       string `json:"speed,omitempty"`
	ElapsedTime int    `json:"elapsed_time"`
	FilePath    string `json:"file_path,omitempty"`
	Error       string `json:"error,omitempty"`
	VideoURL    string `json:"video_url"`
	CreatedAt   string `json:"created_at"`
	UpdatedAt   string `json:"updated_at"`
}

type TranscribeTask struct {
	ID          string `json:"id"`
	Status      string `json:"status"`
	Percentage  int    `json:"percentage"`
	Stage       string `json:"stage,omitempty"`
	ElapsedTime int    `json:"elapsed_time"`
	MP3Path     string `json:"mp3_path,omitempty"`
	TXTPath     string `json:"txt_path,omitempty"`
	Error       string `json:"error,omitempty"`
	VideoPath   string `json:"video_path"`
	CreatedAt   string `json:"created_at"`
	UpdatedAt   string `json:"updated_at"`
}

var (
	db          *sql.DB
	mu          = &sync.RWMutex{}
	taskCounter = 0
)

func getDBPath() string {
	// 数据库存放在项目目录
	return filepath.Join(filepath.Dir(os.Args[0]), "zhihu_downloader.db")
}

func initDB() error {
	var err error
	db, err = sql.Open("sqlite3", getDBPath())
	if err != nil {
		return err
	}

	// 创建下载任务表
	_, err = db.Exec(`
		CREATE TABLE IF NOT EXISTS download_tasks (
			id TEXT PRIMARY KEY,
			status TEXT NOT NULL,
			percentage INTEGER DEFAULT 0,
			speed TEXT,
			elapsed_time INTEGER DEFAULT 0,
			file_path TEXT,
			error TEXT,
			video_url TEXT NOT NULL,
			created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
			updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
		)
	`)
	if err != nil {
		return err
	}

	// 创建转录任务表
	_, err = db.Exec(`
		CREATE TABLE IF NOT EXISTS transcribe_tasks (
			id TEXT PRIMARY KEY,
			status TEXT NOT NULL,
			percentage INTEGER DEFAULT 0,
			stage TEXT,
			elapsed_time INTEGER DEFAULT 0,
			mp3_path TEXT,
			txt_path TEXT,
			error TEXT,
			video_path TEXT NOT NULL,
			created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
			updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
		)
	`)
	if err != nil {
		return err
	}

	// 获取最大的任务计数器
	var maxDL, maxTR sql.NullInt64
	db.QueryRow("SELECT MAX(CAST(SUBSTR(id, 4) AS INTEGER)) FROM download_tasks WHERE id LIKE 'dl-%'").Scan(&maxDL)
	db.QueryRow("SELECT MAX(CAST(SUBSTR(id, 4) AS INTEGER)) FROM transcribe_tasks WHERE id LIKE 'tr-%'").Scan(&maxTR)

	if maxDL.Valid && int(maxDL.Int64) > taskCounter {
		taskCounter = int(maxDL.Int64)
	}
	if maxTR.Valid && int(maxTR.Int64) > taskCounter {
		taskCounter = int(maxTR.Int64)
	}

	return nil
}

// 保存下载任务到数据库
func saveDownloadTask(task *DownloadTask) error {
	_, err := db.Exec(`
		INSERT OR REPLACE INTO download_tasks 
		(id, status, percentage, speed, elapsed_time, file_path, error, video_url, created_at, updated_at)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, COALESCE((SELECT created_at FROM download_tasks WHERE id = ?), CURRENT_TIMESTAMP), CURRENT_TIMESTAMP)
	`, task.ID, task.Status, task.Percentage, task.Speed, task.ElapsedTime, task.FilePath, task.Error, task.VideoURL, task.ID)
	return err
}

// 获取下载任务
func getDownloadTask(taskID string) (*DownloadTask, error) {
	task := &DownloadTask{}
	err := db.QueryRow(`
		SELECT id, status, percentage, COALESCE(speed, ''), elapsed_time, 
		       COALESCE(file_path, ''), COALESCE(error, ''), video_url,
		       created_at, updated_at
		FROM download_tasks WHERE id = ?
	`, taskID).Scan(&task.ID, &task.Status, &task.Percentage, &task.Speed, &task.ElapsedTime,
		&task.FilePath, &task.Error, &task.VideoURL, &task.CreatedAt, &task.UpdatedAt)
	if err != nil {
		return nil, err
	}
	return task, nil
}

// 保存转录任务到数据库
func saveTranscribeTask(task *TranscribeTask) error {
	_, err := db.Exec(`
		INSERT OR REPLACE INTO transcribe_tasks 
		(id, status, percentage, stage, elapsed_time, mp3_path, txt_path, error, video_path, created_at, updated_at)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE((SELECT created_at FROM transcribe_tasks WHERE id = ?), CURRENT_TIMESTAMP), CURRENT_TIMESTAMP)
	`, task.ID, task.Status, task.Percentage, task.Stage, task.ElapsedTime, task.MP3Path, task.TXTPath, task.Error, task.VideoPath, task.ID)
	return err
}

// 获取转录任务
func getTranscribeTask(taskID string) (*TranscribeTask, error) {
	task := &TranscribeTask{}
	err := db.QueryRow(`
		SELECT id, status, percentage, COALESCE(stage, ''), elapsed_time, 
		       COALESCE(mp3_path, ''), COALESCE(txt_path, ''), COALESCE(error, ''), video_path,
		       created_at, updated_at
		FROM transcribe_tasks WHERE id = ?
	`, taskID).Scan(&task.ID, &task.Status, &task.Percentage, &task.Stage, &task.ElapsedTime,
		&task.MP3Path, &task.TXTPath, &task.Error, &task.VideoPath, &task.CreatedAt, &task.UpdatedAt)
	if err != nil {
		return nil, err
	}
	return task, nil
}

// 获取所有下载任务
func getAllDownloadTasks() ([]*DownloadTask, error) {
	rows, err := db.Query(`
		SELECT id, status, percentage, COALESCE(speed, ''), elapsed_time, 
		       COALESCE(file_path, ''), COALESCE(error, ''), video_url,
		       created_at, updated_at
		FROM download_tasks ORDER BY created_at DESC
	`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var tasks []*DownloadTask
	for rows.Next() {
		task := &DownloadTask{}
		err := rows.Scan(&task.ID, &task.Status, &task.Percentage, &task.Speed, &task.ElapsedTime,
			&task.FilePath, &task.Error, &task.VideoURL, &task.CreatedAt, &task.UpdatedAt)
		if err != nil {
			continue
		}
		tasks = append(tasks, task)
	}
	return tasks, nil
}

// 获取所有转录任务
func getAllTranscribeTasks() ([]*TranscribeTask, error) {
	rows, err := db.Query(`
		SELECT id, status, percentage, COALESCE(stage, ''), elapsed_time, 
		       COALESCE(mp3_path, ''), COALESCE(txt_path, ''), COALESCE(error, ''), video_path,
		       created_at, updated_at
		FROM transcribe_tasks ORDER BY created_at DESC
	`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var tasks []*TranscribeTask
	for rows.Next() {
		task := &TranscribeTask{}
		err := rows.Scan(&task.ID, &task.Status, &task.Percentage, &task.Stage, &task.ElapsedTime,
			&task.MP3Path, &task.TXTPath, &task.Error, &task.VideoPath, &task.CreatedAt, &task.UpdatedAt)
		if err != nil {
			continue
		}
		tasks = append(tasks, task)
	}
	return tasks, nil
}

func main() {
	// 初始化数据库
	if err := initDB(); err != nil {
		fmt.Fprintf(os.Stderr, "数据库初始化失败: %v\n", err)
		os.Exit(1)
	}
	defer db.Close()

	reader := bufio.NewReader(os.Stdin)

	for {
		line, err := reader.ReadString('\n')
		if err != nil {
			break
		}

		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}

		var request JSONRPCRequest
		if err := json.Unmarshal([]byte(line), &request); err != nil {
			sendError(nil, -32700, "解析错误")
			continue
		}

		handleRequest(request)
	}
}

func handleRequest(req JSONRPCRequest) {
	switch req.Method {
	case "initialize":
		handleInitialize(req)
	case "notifications/initialized":
		return
	case "tools/list":
		handleToolsList(req)
	case "tools/call":
		handleToolsCall(req)
	case "ping":
		sendResponse(req.ID, map[string]interface{}{})
	default:
		if req.ID == nil {
			return
		}
		sendError(req.ID, -32601, "方法不存在")
	}
}

func handleInitialize(req JSONRPCRequest) {
	result := map[string]interface{}{
		"protocolVersion": "2024-11-05",
		"capabilities": map[string]interface{}{
			"tools": map[string]bool{},
		},
		"serverInfo": map[string]string{
			"name":    "zhihu-downloader",
			"version": "1.0.0",
		},
	}
	sendResponse(req.ID, result)
}

func handleToolsList(req JSONRPCRequest) {
	tools := []map[string]interface{}{
		{
			"name":        "download_video",
			"description": "下载知乎视频为 MP4 格式（默认最高清晰度）",
			"inputSchema": map[string]interface{}{
				"type": "object",
				"properties": map[string]interface{}{
					"url": map[string]interface{}{
						"type":        "string",
						"description": "知乎视频 URL",
					},
					"output_dir": map[string]interface{}{
						"type":        "string",
						"description": "输出目录（默认 ~/Downloads）",
					},
					"filename": map[string]interface{}{
						"type":        "string",
						"description": "输出文件名（不含扩展名，默认 video_任务ID）",
					},
				},
				"required": []string{"url"},
			},
		},
		{
			"name":        "transcribe_video",
			"description": "将视频转录为文本（包括音频提取和 Whisper 转录）",
			"inputSchema": map[string]interface{}{
				"type": "object",
				"properties": map[string]interface{}{
					"video_path": map[string]interface{}{
						"type":        "string",
						"description": "MP4 视频文件路径",
					},
					"output_dir": map[string]interface{}{
						"type":        "string",
						"description": "输出目录（默认与视频同目录）",
					},
					"output_filename": map[string]interface{}{
						"type":        "string",
						"description": "输出文件名（不含扩展名，默认与视频同名）",
					},
					"language": map[string]interface{}{
						"type":        "string",
						"description": "语言代码（默认 zh 中文）",
					},
				},
				"required": []string{"video_path"},
			},
		},
		{
			"name":        "get_progress",
			"description": "获取下载或转录任务的进度",
			"inputSchema": map[string]interface{}{
				"type": "object",
				"properties": map[string]interface{}{
					"task_id": map[string]interface{}{
						"type":        "string",
						"description": "任务 ID",
					},
					"task_type": map[string]interface{}{
						"type":        "string",
						"enum":        []string{"download", "transcribe"},
						"description": "任务类型",
					},
				},
				"required": []string{"task_id", "task_type"},
			},
		},
		{
			"name":        "list_tasks",
			"description": "列出所有任务（下载和转录）",
			"inputSchema": map[string]interface{}{
				"type":       "object",
				"properties": map[string]interface{}{},
			},
		},
	}
	sendResponse(req.ID, map[string]interface{}{"tools": tools})
}

func handleToolsCall(req JSONRPCRequest) {
	var params struct {
		Name      string                 `json:"name"`
		Arguments map[string]interface{} `json:"arguments"`
	}

	if err := json.Unmarshal(req.Params, &params); err != nil {
		sendError(req.ID, -32602, "参数无效")
		return
	}

	var result interface{}
	var err error

	switch params.Name {
	case "download_video":
		result, err = callDownloadVideo(params.Arguments)
	case "transcribe_video":
		result, err = callTranscribeVideo(params.Arguments)
	case "get_progress":
		result, err = callGetProgress(params.Arguments)
	case "list_tasks":
		result, err = callListTasks()
	default:
		sendError(req.ID, -32602, "未知工具")
		return
	}

	if err != nil {
		sendError(req.ID, -32000, err.Error())
		return
	}

	sendResponse(req.ID, map[string]interface{}{
		"content": []map[string]interface{}{
			{
				"type": "text",
				"text": formatResult(result),
			},
		},
	})
}

func callDownloadVideo(args map[string]interface{}) (interface{}, error) {
	url, _ := args["url"].(string)
	if url == "" {
		return nil, fmt.Errorf("URL 必填")
	}

	outputDir, _ := args["output_dir"].(string)
	if outputDir == "" {
		outputDir = filepath.Join(os.Getenv("HOME"), "Downloads")
	}
	// 展开 ~
	if strings.HasPrefix(outputDir, "~") {
		outputDir = filepath.Join(os.Getenv("HOME"), outputDir[1:])
	}

	filename, _ := args["filename"].(string)

	mu.Lock()
	taskCounter++
	taskID := fmt.Sprintf("dl-%d", taskCounter)
	mu.Unlock()

	// 如果没有指定文件名，使用默认
	if filename == "" {
		filename = fmt.Sprintf("video_%s", taskID)
	}

	task := &DownloadTask{
		ID:       taskID,
		Status:   "pending",
		VideoURL: url,
	}

	if err := saveDownloadTask(task); err != nil {
		return nil, fmt.Errorf("保存任务失败: %v", err)
	}

	go downloadVideoWorker(taskID, url, outputDir, filename)

	return map[string]interface{}{
		"task_id":    taskID,
		"output_dir": outputDir,
		"filename":   filename + ".mp4",
		"status":     "已启动下载任务，请使用 get_progress 查看进度",
	}, nil
}

func callTranscribeVideo(args map[string]interface{}) (interface{}, error) {
	videoPath, _ := args["video_path"].(string)
	if videoPath == "" {
		return nil, fmt.Errorf("video_path 必填")
	}
	// 展开 ~
	if strings.HasPrefix(videoPath, "~") {
		videoPath = filepath.Join(os.Getenv("HOME"), videoPath[1:])
	}

	language, _ := args["language"].(string)
	if language == "" {
		language = "zh"
	}

	outputDir, _ := args["output_dir"].(string)
	if outputDir == "" {
		outputDir = filepath.Dir(videoPath)
	}
	// 展开 ~
	if strings.HasPrefix(outputDir, "~") {
		outputDir = filepath.Join(os.Getenv("HOME"), outputDir[1:])
	}

	outputFilename, _ := args["output_filename"].(string)
	if outputFilename == "" {
		// 使用视频文件名（不含扩展名）
		outputFilename = strings.TrimSuffix(filepath.Base(videoPath), filepath.Ext(videoPath))
	}

	if _, err := os.Stat(videoPath); err != nil {
		return nil, fmt.Errorf("视频文件不存在: %v", err)
	}

	mu.Lock()
	taskCounter++
	taskID := fmt.Sprintf("tr-%d", taskCounter)
	mu.Unlock()

	task := &TranscribeTask{
		ID:        taskID,
		Status:    "pending",
		Stage:     "等待开始",
		VideoPath: videoPath,
	}

	if err := saveTranscribeTask(task); err != nil {
		return nil, fmt.Errorf("保存任务失败: %v", err)
	}

	go transcribeVideoWorker(taskID, videoPath, outputDir, outputFilename, language)

	return map[string]interface{}{
		"task_id":         taskID,
		"output_dir":      outputDir,
		"output_filename": outputFilename,
		"mp3_path":        filepath.Join(outputDir, outputFilename+".mp3"),
		"txt_path":        filepath.Join(outputDir, outputFilename+".txt"),
		"status":          "已启动转录任务，请使用 get_progress 查看进度",
	}, nil
}

func callGetProgress(args map[string]interface{}) (interface{}, error) {
	taskID, _ := args["task_id"].(string)
	taskType, _ := args["task_type"].(string)

	if taskID == "" || taskType == "" {
		return nil, fmt.Errorf("task_id 和 task_type 必填")
	}

	if taskType == "download" {
		task, err := getDownloadTask(taskID)
		if err != nil {
			return nil, fmt.Errorf("下载任务不存在")
		}
		return task, nil
	} else if taskType == "transcribe" {
		task, err := getTranscribeTask(taskID)
		if err != nil {
			return nil, fmt.Errorf("转录任务不存在")
		}
		return task, nil
	}

	return nil, fmt.Errorf("未知任务类型")
}

func callListTasks() (interface{}, error) {
	downloads, err := getAllDownloadTasks()
	if err != nil {
		downloads = []*DownloadTask{}
	}

	transcribes, err := getAllTranscribeTasks()
	if err != nil {
		transcribes = []*TranscribeTask{}
	}

	return map[string]interface{}{
		"downloads":   downloads,
		"transcribes": transcribes,
		"summary": map[string]int{
			"total_downloads":   len(downloads),
			"total_transcribes": len(transcribes),
		},
	}, nil
}

func downloadVideoWorker(taskID, url, outputDir, filename string) {
	startTime := time.Now()

	// 更新状态为下载中
	task := &DownloadTask{
		ID:       taskID,
		Status:   "downloading",
		VideoURL: url,
	}
	saveDownloadTask(task)

	os.MkdirAll(outputDir, 0755)

	// 获取脚本目录
	execPath, _ := os.Executable()
	scriptDir := filepath.Dir(execPath)
	pythonScript := filepath.Join(scriptDir, "zhihu_downloader.py")
	venvPython := filepath.Join(scriptDir, ".venv", "bin", "python")

	// 使用 Python 知乎下载器（支持 cookies 认证）
	cmd := exec.Command(venvPython, pythonScript, url, "-o", outputDir, "-q", "fhd")

	// 获取 stdout 管道实时读取进度
	stdout, _ := cmd.StdoutPipe()
	cmd.Stderr = cmd.Stdout // 合并 stderr 到 stdout

	if err := cmd.Start(); err != nil {
		task.Status = "failed"
		task.Error = fmt.Sprintf("启动失败: %v", err)
		task.ElapsedTime = int(time.Since(startTime).Seconds())
		saveDownloadTask(task)
		return
	}

	// 实时读取输出并解析进度
	scanner := bufio.NewScanner(stdout)
	var lastOutput strings.Builder
	// 百分比匹配正则
	percentRe := regexp.MustCompile(`(\d+\.?\d*)%`)

	for scanner.Scan() {
		line := scanner.Text()
		lastOutput.WriteString(line + "\n")

		// 解析进度: 匹配任何包含百分比的行
		// 支持格式: "下载进度: 77.1%", "下载中... 77%", "77.1%" 等
		if matches := percentRe.FindStringSubmatch(line); len(matches) > 1 {
			if pct, err := strconv.ParseFloat(matches[1], 64); err == nil {
				// 只在进度增加时更新，避免频繁写数据库
				if int(pct) > task.Percentage {
					task.Percentage = int(pct)
					task.ElapsedTime = int(time.Since(startTime).Seconds())
					if task.ElapsedTime > 0 {
						// 计算下载速度（估算）
						task.Speed = fmt.Sprintf("%.1f%%/s", float64(task.Percentage)/float64(task.ElapsedTime))
					}
					saveDownloadTask(task)
				}
			}
		}
	}

	err := cmd.Wait()
	task.ElapsedTime = int(time.Since(startTime).Seconds())

	if err != nil {
		task.Status = "failed"
		task.Error = fmt.Sprintf("%v: %s", err, lastOutput.String())
	} else {
		// 查找下载的 mp4 文件（Python 脚本会自动命名）
		matches, _ := filepath.Glob(filepath.Join(outputDir, "*.mp4"))
		if len(matches) > 0 {
			// 找最新的文件
			var latestFile string
			var latestTime time.Time
			for _, m := range matches {
				info, err := os.Stat(m)
				if err == nil && info.ModTime().After(latestTime) {
					latestTime = info.ModTime()
					latestFile = m
				}
			}
			if latestFile != "" && latestTime.After(startTime.Add(-time.Minute)) {
				task.Status = "completed"
				task.Percentage = 100
				task.FilePath = latestFile
			} else {
				task.Status = "failed"
				task.Error = "未找到新下载的文件"
			}
		} else {
			task.Status = "failed"
			task.Error = "文件为空或不存在"
		}
	}

	saveDownloadTask(task)
}

func transcribeVideoWorker(taskID, videoPath, outputDir, outputFilename, language string) {
	startTime := time.Now()

	// 先获取视频时长（秒）
	videoDuration := getVideoDuration(videoPath)
	if videoDuration <= 0 {
		videoDuration = 3600 // 默认假设 1 小时
	}

	// 更新状态为提取音频
	task := &TranscribeTask{
		ID:         taskID,
		Status:     "extracting_audio",
		Stage:      fmt.Sprintf("正在提取音频（视频时长 %.0f 分钟）...", float64(videoDuration)/60),
		Percentage: 1,
		VideoPath:  videoPath,
	}
	saveTranscribeTask(task)

	os.MkdirAll(outputDir, 0755)
	mp3Path := filepath.Join(outputDir, outputFilename+".mp3")

	// 用 ffmpeg 提取音频
	ffmpegCmd := exec.Command("ffmpeg", "-y", "-i", videoPath, "-q:a", "9", mp3Path)
	ffmpegCmd.Stdout = nil
	ffmpegCmd.Stderr = nil

	if err := ffmpegCmd.Start(); err != nil {
		task.Status = "failed"
		task.Error = fmt.Sprintf("音频提取启动失败: %v", err)
		task.ElapsedTime = int(time.Since(startTime).Seconds())
		saveTranscribeTask(task)
		return
	}

	// 在等待 ffmpeg 的同时，根据文件大小估算进度
	go func() {
		for {
			if ffmpegCmd.ProcessState != nil {
				break
			}
			if info, err := os.Stat(mp3Path); err == nil {
				// 估算：1 分钟音频约 1MB MP3
				expectedSize := float64(videoDuration) / 60 * 1024 * 1024
				if expectedSize > 0 {
					pct := int(float64(info.Size()) / expectedSize * 15) // 音频提取占 0-15%
					if pct > 15 {
						pct = 15
					}
					if pct > task.Percentage {
						task.Percentage = pct
						task.ElapsedTime = int(time.Since(startTime).Seconds())
						saveTranscribeTask(task)
					}
				}
			}
			time.Sleep(2 * time.Second)
		}
	}()

	if err := ffmpegCmd.Wait(); err != nil {
		task.Status = "failed"
		task.Error = fmt.Sprintf("音频提取失败: %v", err)
		task.ElapsedTime = int(time.Since(startTime).Seconds())
		saveTranscribeTask(task)
		return
	}

	task.Percentage = 15
	task.MP3Path = mp3Path
	task.Stage = "音频提取完成，开始转录..."
	saveTranscribeTask(task)

	// 更新状态为转录中
	task.Status = "transcribing"
	task.Stage = "正在转录（Whisper base 模型）..."
	task.Percentage = 16
	saveTranscribeTask(task)

	// 实时输出的 txt 文件路径
	realtimeTxtPath := filepath.Join(outputDir, outputFilename+".txt")
	task.TXTPath = realtimeTxtPath
	saveTranscribeTask(task)

	// 创建/清空实时输出文件
	txtFile, err := os.Create(realtimeTxtPath)
	if err != nil {
		task.Status = "failed"
		task.Error = fmt.Sprintf("创建输出文件失败: %v", err)
		task.ElapsedTime = int(time.Since(startTime).Seconds())
		saveTranscribeTask(task)
		return
	}
	defer txtFile.Close()

	// 使用 mlx-whisper (Apple Silicon GPU 加速)
	mlxWhisperPath := "/Users/oasmet/Library/Python/3.14/bin/mlx_whisper"
	whisperCmd := exec.Command("bash", "-c",
		fmt.Sprintf("export PATH=/opt/homebrew/bin:$PATH && %s %q --output-format txt --output-dir %q --language %s --model mlx-community/whisper-base-mlx --verbose True 2>&1",
			mlxWhisperPath, mp3Path, outputDir, language))

	whisperStdout, _ := whisperCmd.StdoutPipe()

	if err := whisperCmd.Start(); err != nil {
		task.Status = "failed"
		task.Error = fmt.Sprintf("转录启动失败: %v", err)
		task.ElapsedTime = int(time.Since(startTime).Seconds())
		saveTranscribeTask(task)
		return
	}

	// 解析 Whisper 进度：[00:00.000 --> 00:30.000] 文本内容 格式
	whisperScanner := bufio.NewScanner(whisperStdout)
	// 时间戳正则：匹配 [开始时间 --> 结束时间] 并提取后面的文本
	timeRe := regexp.MustCompile(`\[(\d{2}):(\d{2})\.(\d{3})\s*-->\s*(\d{2}):(\d{2})\.(\d{3})\]\s*(.*)`)

	for whisperScanner.Scan() {
		line := whisperScanner.Text()

		// 解析时间戳和文本
		if matches := timeRe.FindStringSubmatch(line); len(matches) >= 7 {
			// 解析结束时间（第 4、5、6 组）
			endMin, _ := strconv.Atoi(matches[4])
			endSec, _ := strconv.Atoi(matches[5])
			endMs, _ := strconv.Atoi(matches[6])
			currentSec := float64(endMin*60+endSec) + float64(endMs)/1000

			// 提取转录文本（第 7 组）
			transcribedText := ""
			if len(matches) >= 8 {
				transcribedText = strings.TrimSpace(matches[7])
			}

			// 实时写入 txt 文件（只写文本，不写时间戳）
			if transcribedText != "" {
				txtFile.WriteString(transcribedText + "\n")
				txtFile.Sync() // 确保立即写入磁盘
			}

			// 计算进度（转录占 16%-98%）
			if videoDuration > 0 {
				pct := 16 + int(currentSec/float64(videoDuration)*82)
				if pct > 98 {
					pct = 98
				}
				if pct > task.Percentage {
					task.Percentage = pct
					task.Stage = fmt.Sprintf("转录中: %02d:%02d / %02d:%02d", endMin, endSec, int(videoDuration)/60, int(videoDuration)%60)
					task.ElapsedTime = int(time.Since(startTime).Seconds())
					saveTranscribeTask(task)
				}
			}
		}
	}

	if err := whisperCmd.Wait(); err != nil {
		task.Status = "failed"
		task.Error = fmt.Sprintf("转录失败: %v", err)
		task.ElapsedTime = int(time.Since(startTime).Seconds())
		saveTranscribeTask(task)
		return
	}

	// mlx-whisper 也会生成自己的输出文件，但我们用的是实时写入的版本
	whisperOutputTxt := realtimeTxtPath

	task.Status = "completed"
	task.Percentage = 100
	task.Stage = "转录完成"
	task.TXTPath = whisperOutputTxt
	task.ElapsedTime = int(time.Since(startTime).Seconds())
	saveTranscribeTask(task)
}

// 获取视频时长（秒）
func getVideoDuration(videoPath string) float64 {
	cmd := exec.Command("ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", videoPath)
	output, err := cmd.Output()
	if err != nil {
		return 0
	}
	duration, err := strconv.ParseFloat(strings.TrimSpace(string(output)), 64)
	if err != nil {
		return 0
	}
	return duration
}

func formatResult(result interface{}) string {
	data, _ := json.MarshalIndent(result, "", "  ")
	return string(data)
}

func sendResponse(id interface{}, result interface{}) {
	response := JSONRPCResponse{
		JSONRPC: "2.0",
		ID:      id,
		Result:  result,
	}
	data, _ := json.Marshal(response)
	fmt.Println(string(data))
}

func sendError(id interface{}, code int, message string) {
	if id == nil {
		return
	}
	response := JSONRPCResponse{
		JSONRPC: "2.0",
		ID:      id,
		Error: &RPCError{
			Code:    code,
			Message: message,
		},
	}
	data, _ := json.Marshal(response)
	fmt.Println(string(data))
}
