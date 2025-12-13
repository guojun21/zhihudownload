import { useState, useEffect, useCallback, useRef } from 'react';
import { 
  Download, 
  Settings, 
  X, 
  Check, 
  Loader2, 
  AlertCircle, 
  Link2, 
  FolderOpen,
  Cookie,
  ChevronRight,
  Play,
  ExternalLink
} from 'lucide-react';
import { api } from './api/zhihu';
import type { VideoInfo, DownloadOption, DownloadItem } from './types';
import './App.css';

function App() {
  const [url, setUrl] = useState('');
  const [videoInfo, setVideoInfo] = useState<VideoInfo | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [downloads, setDownloads] = useState<DownloadItem[]>([]);
  const [showSettings, setShowSettings] = useState(false);
  const [authenticated, setAuthenticated] = useState(false);
  const [outputPath, setOutputPath] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // 检查认证状态
  useEffect(() => {
    checkAuth();
  }, []);

  const checkAuth = async () => {
    try {
      const result = await api.checkCookies();
      setAuthenticated(result.authenticated);
    } catch {
      setAuthenticated(false);
    }
  };

  // 解析视频
  const handleParse = async () => {
    const urlToParse = url.trim();
    if (!urlToParse) {
      setError('请输入视频 URL');
      return;
    }
    
    console.log('开始解析视频:', urlToParse);
    setLoading(true);
    setError(null);
    setVideoInfo(null);
    
    try {
      console.log('调用 API parseVideo...');
      const info = await api.parseVideo(urlToParse);
      console.log('解析成功:', info);
      setVideoInfo(info);
    } catch (err: unknown) {
      console.error('解析失败:', err);
      let errorMessage = '解析失败';
      
      if (err && typeof err === 'object') {
        if ('response' in err) {
          const response = (err as { response?: { data?: { detail?: string }; status?: number } }).response;
          if (response?.data?.detail) {
            errorMessage = response.data.detail;
          } else if (response?.status === 500) {
            errorMessage = '服务器错误，请检查后端服务是否正常运行';
          } else if (response?.status === 400) {
            errorMessage = '请求参数错误';
          } else if (response?.status) {
            errorMessage = `请求失败 (${response.status})`;
          }
        } else if ('message' in err) {
          errorMessage = (err as { message: string }).message;
        }
      } else if (err instanceof Error) {
        errorMessage = err.message;
      }
      
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  // 开始下载
  const handleDownload = async (option: DownloadOption) => {
    if (!videoInfo) return;

    try {
      const downloadId = await api.startDownload(
        url,
        option.quality,
        outputPath || undefined
      );

      const newDownload: DownloadItem = {
        id: `${videoInfo.video_id}-${Date.now()}`,
        downloadId,
        url,
        title: videoInfo.title,
        quality: option.quality,
        progress: { status: 'Starting', percentage: 0 },
      };

      setDownloads(prev => [newDownload, ...prev]);
      setVideoInfo(null);
      setUrl('');
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : '下载失败';
      setError(errorMessage);
    }
  };

  // 轮询下载进度
  const updateProgress = useCallback(async () => {
    const activeDownloads = downloads.filter(
      d => d.progress.status !== 'Completed' && d.progress.status !== 'Failed'
    );

    for (const download of activeDownloads) {
      try {
        const progress = await api.getProgress(download.downloadId);
        setDownloads(prev =>
          prev.map(d =>
            d.id === download.id ? { ...d, progress } : d
          )
        );
      } catch {
        // 忽略错误
      }
    }
  }, [downloads]);

  useEffect(() => {
    const interval = setInterval(updateProgress, 1000);
    return () => clearInterval(interval);
  }, [updateProgress]);

  // 选择输出目录
  const handleSelectDirectory = async () => {
    const path = await window.electronAPI?.selectDirectory();
    if (path) {
      setOutputPath(path);
    }
  };

  // 打开文件位置
  const handleOpenFile = (filePath: string) => {
    window.electronAPI?.openFile(filePath);
  };

  // 格式化时长
  const formatDuration = (ms: number) => {
    const seconds = Math.floor(ms / 1000);
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    
    if (h > 0) {
      return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    }
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  return (
    <div className="app">
      {/* 标题栏拖拽区域 */}
      <div className="drag-region" />

      {/* 头部 */}
      <header className="header">
        <div className="logo">
          <Download size={24} />
          <span>知乎视频下载器</span>
        </div>
        <button 
          className={`settings-btn ${authenticated ? 'authenticated' : ''}`}
          onClick={() => setShowSettings(true)}
        >
          <Settings size={20} />
        </button>
      </header>

      {/* 错误提示 */}
      {error && (
        <div className="error-banner">
          <AlertCircle size={16} />
          <span>{error}</span>
          <button onClick={() => setError(null)}><X size={16} /></button>
        </div>
      )}

      {/* 主内容 */}
      <main className="main">
        {/* URL 输入区域 */}
        <section className="input-section">
          <div className="input-wrapper">
            <Link2 className="input-icon" size={20} />
            <input
              ref={inputRef}
              type="text"
              value={url}
              onChange={e => {
                const newUrl = e.target.value;
                console.log('输入框值变化:', newUrl);
                setUrl(newUrl);
              }}
              onPaste={e => {
                const pastedText = e.clipboardData.getData('text');
                console.log('粘贴内容:', pastedText);
                setUrl(pastedText);
              }}
              placeholder="粘贴知乎视频 URL..."
              onKeyDown={e => {
                if (e.key === 'Enter') {
                  console.log('按Enter键，当前URL:', url);
                  handleParse();
                }
              }}
            />
            <button 
              className="parse-btn"
              onClick={handleParse} 
              disabled={loading || !url.trim()}
            >
              {loading ? <Loader2 className="spin" size={18} /> : '解析'}
            </button>
          </div>
          
          <div className="output-path" onClick={handleSelectDirectory}>
            <FolderOpen size={16} />
            <span>{outputPath || '默认下载目录 (~/Downloads)'}</span>
            <ChevronRight size={16} />
          </div>
        </section>

        {/* 视频信息 */}
        {videoInfo && (
          <section className="video-section">
            <div className="video-card">
              <div className="video-header">
                <div className="video-icon">
                  <Play size={24} />
                </div>
                <div className="video-meta">
                  <h3>{videoInfo.title}</h3>
                  <p>时长: {formatDuration(videoInfo.duration)}</p>
                </div>
              </div>
              
              <div className="options-list">
                <h4>选择清晰度</h4>
                {videoInfo.options.map((option, index) => (
                  <button
                    key={index}
                    className="option-btn"
                    onClick={() => handleDownload(option)}
                  >
                    <span className="option-quality">
                      {option.quality.toUpperCase()}
                    </span>
                    <span className="option-size">{option.size}</span>
                    <span className="option-format">{option.format}</span>
                    <Download size={16} />
                  </button>
                ))}
              </div>
            </div>
          </section>
        )}

        {/* 下载列表 */}
        {downloads.length > 0 && (
          <section className="downloads-section">
            <h2>
              <Download size={18} />
              下载任务
            </h2>
            <div className="downloads-list">
              {downloads.map(download => (
                <div key={download.id} className="download-item">
                  <div className="download-icon">
                    {download.progress.status === 'Completed' ? (
                      <Check size={20} />
                    ) : download.progress.status === 'Failed' ? (
                      <AlertCircle size={20} />
                    ) : (
                      <Loader2 className="spin" size={20} />
                    )}
                  </div>
                  <div className="download-info">
                    <h4>{download.title}</h4>
                    <p>{download.quality.toUpperCase()}</p>
                    {download.progress.status !== 'Completed' && download.progress.status !== 'Failed' && (
                      <div className="progress-bar">
                        <div 
                          className="progress-fill"
                          style={{ width: `${download.progress.percentage}%` }}
                        />
                      </div>
                    )}
                    <span className={`status status-${download.progress.status.toLowerCase()}`}>
                      {download.progress.status === 'Completed' 
                        ? '下载完成' 
                        : download.progress.status === 'Failed'
                        ? download.progress.error || '下载失败'
                        : `${download.progress.percentage}%`}
                    </span>
                  </div>
                  {download.progress.status === 'Completed' && download.progress.file_path && (
                    <button 
                      className="open-btn"
                      onClick={() => handleOpenFile(download.progress.file_path!)}
                    >
                      <ExternalLink size={16} />
                    </button>
                  )}
                </div>
              ))}
            </div>
          </section>
        )}

        {/* 加载状态 */}
        {loading && (
          <div className="empty-state">
            <Loader2 className="spin" size={64} strokeWidth={1} />
            <h2>正在解析视频...</h2>
            <p>请稍候</p>
          </div>
        )}

        {/* 空状态 */}
        {!videoInfo && downloads.length === 0 && !loading && (
          <div className="empty-state">
            <Download size={64} strokeWidth={1} />
            <h2>知乎视频下载器</h2>
            <p>粘贴知乎训练营视频 URL 开始下载</p>
            {!authenticated && (
              <div className="auth-hint">
                <Cookie size={16} />
                <span>提示: 点击右上角设置按钮配置登录状态</span>
              </div>
            )}
          </div>
        )}
      </main>

      {/* 设置弹窗 */}
      {showSettings && (
        <div className="modal-overlay" onClick={() => setShowSettings(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <button className="modal-close" onClick={() => setShowSettings(false)}>
              <X size={20} />
            </button>
            <div className="modal-header">
              <Settings size={24} />
              <h3>设置</h3>
            </div>
            <div className="modal-body">
              <div className="setting-item">
                <div className="setting-label">
                  <Cookie size={18} />
                  <span>登录状态</span>
                </div>
                <div className={`setting-status ${authenticated ? 'authenticated' : ''}`}>
                  {authenticated ? (
                    <>
                      <Check size={16} />
                      <span>已认证</span>
                    </>
                  ) : (
                    <>
                      <AlertCircle size={16} />
                      <span>未认证</span>
                    </>
                  )}
                </div>
              </div>
              
              <div className="setting-hint">
                <p>下载付费视频需要登录知乎账号。</p>
                <p>请确保已在 Chrome 中登录知乎，程序会自动读取 cookies。</p>
                <p>如果无法自动读取，请参考 README 手动配置。</p>
              </div>

              <div className="setting-item">
                <div className="setting-label">
                  <FolderOpen size={18} />
                  <span>下载目录</span>
                </div>
                <button className="setting-action" onClick={handleSelectDirectory}>
                  {outputPath ? '更改' : '选择'}
                </button>
              </div>
              {outputPath && (
                <div className="setting-path">{outputPath}</div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;

