import SwiftUI
import Combine

// MARK: - App Entry

@main
struct ZhihuDownloaderApp: App {
    var body: some Scene {
        WindowGroup("知乎视频下载器") {
            ContentView()
                .frame(minWidth: 800, minHeight: 600)
        }
        .windowStyle(.automatic)
    }
}

// MARK: - Models

struct VideoInfo: Codable {
    let videoId: String
    let title: String
    let duration: Int
    let optionsData: [DownloadOptionCodable]
    
    var options: [DownloadOption] {
        optionsData.map { DownloadOption(quality: $0.quality, size: $0.size, format: $0.format) }
    }
    
    enum CodingKeys: String, CodingKey {
        case videoId = "video_id"
        case title
        case duration
        case optionsData = "options"
    }
}

struct DownloadOptionCodable: Codable {
    let quality: String
    let size: String
    let format: String
}

struct DownloadOption: Identifiable {
    let id = UUID()
    let quality: String
    let size: String
    let format: String
}

struct DownloadProgress: Codable {
    let status: String
    let percentage: Int
    let filePath: String?
    let error: String?
    let speed: String?
    let elapsedTime: Int?
    
    enum CodingKeys: String, CodingKey {
        case status
        case percentage
        case filePath = "file_path"
        case error
        case speed
        case elapsedTime = "elapsed_time"
    }
}

// MARK: - API Service

class APIService: ObservableObject {
    static let shared = APIService()
    let baseURL = "http://127.0.0.1:5124"
    
    func parseVideo(url: String) async throws -> VideoInfo {
        guard let requestURL = URL(string: "\(baseURL)/api/parse") else {
            throw NSError(domain: "Invalid URL", code: -1)
        }
        
        var request = URLRequest(url: requestURL)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let payload = ["url": url]
        request.httpBody = try JSONEncoder().encode(payload)
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw NSError(domain: "API Error", code: -1)
        }
        
        return try JSONDecoder().decode(VideoInfo.self, from: data)
    }
    
    func startDownload(url: String, quality: String, outputPath: String? = nil) async throws -> String {
        guard let requestURL = URL(string: "\(baseURL)/api/download") else {
            throw NSError(domain: "Invalid URL", code: -1)
        }
        
        var request = URLRequest(url: requestURL)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        var payload: [String: Any] = ["url": url, "quality": quality]
        if let outputPath = outputPath {
            payload["output_path"] = outputPath
        }
        
        request.httpBody = try JSONSerialization.data(withJSONObject: payload)
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw NSError(domain: "API Error", code: -1)
        }
        
        struct DownloadResponse: Decodable {
            let id: String
        }
        
        let result = try JSONDecoder().decode(DownloadResponse.self, from: data)
        return result.id
    }
    
    func getProgress(downloadId: String) async throws -> DownloadProgress {
        guard let requestURL = URL(string: "\(baseURL)/api/progress/\(downloadId)") else {
            throw NSError(domain: "Invalid URL", code: -1)
        }
        
        let (data, _) = try await URLSession.shared.data(from: requestURL)
        return try JSONDecoder().decode(DownloadProgress.self, from: data)
    }
    
    func cancelDownload(downloadId: String) async throws {
        guard let requestURL = URL(string: "\(baseURL)/api/download/\(downloadId)/cancel") else {
            throw NSError(domain: "Invalid URL", code: -1)
        }
        
        var request = URLRequest(url: requestURL)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let (_, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw NSError(domain: "API Error", code: -1)
        }
    }
    
    func checkCookies() async throws -> Bool {
        guard let requestURL = URL(string: "\(baseURL)/api/cookies/check") else {
            throw NSError(domain: "Invalid URL", code: -1)
        }
        
        struct CookieResponse: Decodable {
            let authenticated: Bool
        }
        
        let (data, _) = try await URLSession.shared.data(from: requestURL)
        let result = try JSONDecoder().decode(CookieResponse.self, from: data)
        return result.authenticated
    }
}

// MARK: - View Models

class DownloadItem: Identifiable, ObservableObject {
    let id: String
    let downloadId: String
    let url: String
    let title: String
    let quality: String
    @Published var progress: DownloadProgress
    
    init(id: String, downloadId: String, url: String, title: String, quality: String, progress: DownloadProgress) {
        self.id = id
        self.downloadId = downloadId
        self.url = url
        self.title = title
        self.quality = quality
        self.progress = progress
    }
}

// MARK: - Main Content View

struct ContentView: View {
    @StateObject private var api = APIService.shared
    @State private var urlInput: String = ""
    @State private var videoInfo: VideoInfo?
    @State private var isLoading = false
    @State private var errorMessage: String?
    @State private var downloads: [DownloadItem] = []
    @State private var isAuthenticated = false
    @State private var outputPath: String?
    @State private var showSettings = false
    @State private var progressTimer: Timer?
    
    var body: some View {
        ZStack {
            // Main Background
            Color(nsColor: .controlBackgroundColor)
                .ignoresSafeArea()
            
            VStack(spacing: 0) {
                // Header
                headerView
                
                // Error Banner
                if let error = errorMessage {
                    ErrorBannerView(message: error) {
                        errorMessage = nil
                    }
                }
                
                // Main Content
                ScrollView {
                    VStack(spacing: 20) {
                        // URL Input Section
                        inputSection
                        
                        // Video Info Section
                        if let videoInfo = videoInfo {
                            videoInfoSection(videoInfo)
                        }
                        
                        // Downloads Section
                        if !downloads.isEmpty {
                            downloadsSection
                        }
                        
                        // Empty State
                        if videoInfo == nil && downloads.isEmpty && !isLoading {
                            emptyStateView
                        }
                        
                        // Loading State
                        if isLoading {
                            loadingView
                        }
                    }
                    .padding(20)
                }
            }
        }
        .task {
            await checkAuthentication()
            startProgressPolling()
        }
        .onDisappear {
            progressTimer?.invalidate()
        }
    }
    
    // MARK: - Views
    
    private var headerView: some View {
        HStack {
            HStack(spacing: 8) {
                Image(systemName: "arrow.down.circle.fill")
                    .font(.system(size: 20))
                    .foregroundColor(.blue)
                Text("知乎视频下载器")
                    .font(.system(size: 18, weight: .semibold))
            }
            
            Spacer()
            
            Button(action: { showSettings = true }) {
                Image(systemName: "gear")
                    .font(.system(size: 14))
                    .foregroundColor(.gray)
                    .padding(8)
                    .background(Color(nsColor: .controlBackgroundColor))
                    .cornerRadius(6)
                    .overlay(
                        RoundedRectangle(cornerRadius: 6)
                            .stroke(isAuthenticated ? Color.green : Color.gray.opacity(0.3), lineWidth: 1)
                    )
            }
            .buttonStyle(.plain)
        }
        .padding(16)
        .background(Color(nsColor: .gridColor).opacity(0.1))
        .border(.separator, width: 1)
    }
    
    private var inputSection: some View {
        VStack(spacing: 12) {
            HStack(spacing: 12) {
                Image(systemName: "link")
                    .foregroundColor(.gray)
                
                TextField("粘贴知乎视频 URL...", text: $urlInput)
                    .textFieldStyle(.plain)
                
                Button(action: { handleParse() }) {
                    if isLoading {
                        ProgressView()
                            .scaleEffect(0.8)
                    } else {
                        Text("解析")
                            .font(.system(size: 13, weight: .medium))
                    }
                }
                .disabled(isLoading || urlInput.trimmingCharacters(in: .whitespaces).isEmpty)
                .keyboardShortcut(.return, modifiers: [])
            }
            .padding(12)
            .background(Color(nsColor: .gridColor).opacity(0.05))
            .cornerRadius(8)
            .overlay(RoundedRectangle(cornerRadius: 8).stroke(Color.gray.opacity(0.2), lineWidth: 1))
            
            HStack {
                Image(systemName: "folder")
                    .foregroundColor(.gray)
                    .font(.system(size: 14))
                
                Text(outputPath ?? "默认下载目录 (~/Downloads)")
                    .font(.system(size: 13))
                    .foregroundColor(.gray)
                
                Spacer()
                
                Button(action: selectOutputPath) {
                    Text("选择")
                        .font(.system(size: 12, weight: .medium))
                }
                .buttonStyle(.plain)
            }
            .padding(10)
            .background(Color(nsColor: .controlBackgroundColor))
            .cornerRadius(6)
        }
        .padding(12)
        .background(Color(nsColor: .gridColor).opacity(0.05))
        .cornerRadius(12)
    }
    
    private func videoInfoSection(_ info: VideoInfo) -> some View {
        VStack(spacing: 12) {
            HStack(spacing: 12) {
                Image(systemName: "play.circle.fill")
                    .font(.system(size: 24))
                    .foregroundColor(.blue)
                
                VStack(alignment: .leading, spacing: 4) {
                    Text(info.title)
                        .font(.system(size: 14, weight: .semibold))
                        .lineLimit(2)
                    
                    Text("时长: \(formatDuration(info.duration))")
                        .font(.system(size: 12))
                        .foregroundColor(.gray)
                }
                
                Spacer()
            }
            
            VStack(alignment: .leading, spacing: 8) {
                Text("选择清晰度")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundColor(.gray)
                
                ForEach(info.options, id: \.quality) { option in
                    Button(action: { handleDownload(option) }) {
                        HStack(spacing: 12) {
                            VStack(alignment: .leading, spacing: 2) {
                                Text(option.quality.uppercased())
                                    .font(.system(size: 13, weight: .semibold))
                                Text(option.size)
                                    .font(.system(size: 11))
                                    .foregroundColor(.gray)
                            }
                            
                            Spacer()
                            
                            Text(option.format)
                                .font(.system(size: 11))
                                .foregroundColor(.gray)
                            
                            Image(systemName: "arrow.down.circle")
                                .foregroundColor(.blue)
                        }
                        .padding(10)
                        .background(Color(nsColor: .controlBackgroundColor))
                        .cornerRadius(6)
                    }
                    .buttonStyle(.plain)
                }
            }
        }
        .padding(12)
        .background(Color(nsColor: .gridColor).opacity(0.05))
        .cornerRadius(12)
    }
    
    private var downloadsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "arrow.down.circle")
                    .foregroundColor(.blue)
                Text("下载任务")
                    .font(.system(size: 14, weight: .semibold))
                Spacer()
            }
            
            ForEach(downloads, id: \.id) { download in
                DownloadItemView(item: download, api: api) {
                    // 取消后刷新列表
                }
            }
        }
        .padding(12)
        .background(Color(nsColor: .gridColor).opacity(0.05))
        .cornerRadius(12)
    }
    
    private var emptyStateView: some View {
        VStack(spacing: 16) {
            Image(systemName: "arrow.down.circle")
                .font(.system(size: 64))
                .foregroundColor(.gray.opacity(0.5))
            
            Text("知乎视频下载器")
                .font(.system(size: 18, weight: .semibold))
            
            Text("粘贴知乎视频 URL 开始下载")
                .font(.system(size: 13))
                .foregroundColor(.gray)
            
            if !isAuthenticated {
                HStack(spacing: 8) {
                    Image(systemName: "info.circle")
                        .foregroundColor(.orange)
                    Text("提示: 点击右上角设置按钮配置登录状态")
                        .font(.system(size: 12))
                        .foregroundColor(.orange)
                }
                .padding(10)
                .background(Color.orange.opacity(0.1))
                .cornerRadius(6)
            }
        }
        .frame(maxWidth: .infinity)
        .padding(40)
        .foregroundColor(.gray)
    }
    
    private var loadingView: some View {
        VStack(spacing: 16) {
            ProgressView()
            Text("正在解析视频...")
                .font(.system(size: 14))
                .foregroundColor(.gray)
        }
        .frame(maxWidth: .infinity)
        .padding(40)
    }
    
    // MARK: - Actions
    
    private func handleParse() {
        Task {
            isLoading = true
            errorMessage = nil
            
            do {
                videoInfo = try await APIService.shared.parseVideo(url: urlInput)
            } catch {
                errorMessage = "解析失败: \(error.localizedDescription)"
                print("解析错误详情: \(error)")
            }
            
            isLoading = false
        }
    }
    
    private func handleDownload(_ option: DownloadOption) {
        guard let info = videoInfo else { return }
        
        Task {
            do {
                let downloadId = try await APIService.shared.startDownload(
                    url: urlInput,
                    quality: option.quality,
                    outputPath: outputPath
                )
                
                let item = DownloadItem(
                    id: "\(info.videoId)-\(Date().timeIntervalSince1970)",
                    downloadId: downloadId,
                    url: urlInput,
                    title: info.title,
                    quality: option.quality,
                    progress: DownloadProgress(status: "Starting", percentage: 0, filePath: nil, error: nil, speed: nil, elapsedTime: 0)
                )
                
                downloads.insert(item, at: 0)
                videoInfo = nil
                urlInput = ""
            } catch {
                errorMessage = "下载失败: \(error.localizedDescription)"
            }
        }
    }
    
    private func checkAuthentication() async {
        do {
            isAuthenticated = try await APIService.shared.checkCookies()
        } catch {
            isAuthenticated = false
        }
    }
    
    private func selectOutputPath() {
        let panel = NSOpenPanel()
        panel.canChooseDirectories = true
        panel.canChooseFiles = false
        panel.allowsMultipleSelection = false
        
        if panel.runModal() == .OK, let url = panel.url {
            outputPath = url.path
        }
    }
    
    private func startProgressPolling() {
        progressTimer?.invalidate()
        progressTimer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { _ in
            Task { @MainActor in
                for download in self.downloads {
                    if download.progress.status != "Completed" && download.progress.status != "Failed" {
                        do {
                            let progress = try await APIService.shared.getProgress(downloadId: download.downloadId)
                            download.progress = progress
                        } catch {
                            // Silent fail
                        }
                    }
                }
            }
        }
    }
    
    private func formatDuration(_ ms: Int) -> String {
        let seconds = ms / 1000
        let h = seconds / 3600
        let m = (seconds % 3600) / 60
        let s = seconds % 60
        
        if h > 0 {
            return String(format: "%d:%02d:%02d", h, m, s)
        }
        return String(format: "%d:%02d", m, s)
    }
}

// MARK: - Sub-Views

struct ErrorBannerView: View {
    let message: String
    let onDismiss: () -> Void
    
    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: "exclamationmark.circle.fill")
                .foregroundColor(.red)
            
            Text(message)
                .font(.system(size: 12))
                .lineLimit(2)
            
            Spacer()
            
            Button(action: onDismiss) {
                Image(systemName: "xmark")
                    .font(.system(size: 10))
            }
            .buttonStyle(.plain)
        }
        .padding(12)
        .background(Color.red.opacity(0.1))
        .foregroundColor(.red)
        .cornerRadius(8)
        .padding(12)
    }
}

struct DownloadItemView: View {
    @ObservedObject var item: DownloadItem
    let api: APIService
    var onCancel: () -> Void = {}
    
    var statusColor: Color {
        switch item.progress.status {
        case "Completed": return .green
        case "Failed", "Cancelled": return .orange
        default: return .blue
        }
    }
    
    var statusIcon: String {
        switch item.progress.status {
        case "Completed": return "checkmark.circle.fill"
        case "Failed": return "xmark.circle.fill"
        case "Cancelled": return "xmark.circle"
        default: return "arrow.down.circle.fill"
        }
    }
    
    var body: some View {
        VStack(spacing: 8) {
            HStack(spacing: 12) {
                Image(systemName: statusIcon)
                    .foregroundColor(statusColor)
                    .font(.system(size: 18))
                
                VStack(alignment: .leading, spacing: 4) {
                    Text(item.title)
                        .font(.system(size: 13, weight: .semibold))
                        .lineLimit(1)
                    
                    Text(item.quality.uppercased())
                        .font(.system(size: 11))
                        .foregroundColor(.gray)
                }
                
                Spacer()
                
                if item.progress.status == "Downloading" || item.progress.status == "Starting" {
                    Button(action: { handleCancel() }) {
                        Image(systemName: "xmark.circle.fill")
                            .foregroundColor(.red)
                            .font(.system(size: 14))
                    }
                    .buttonStyle(.plain)
                }
                
                Text(statusText)
                    .font(.system(size: 12, weight: .medium))
                    .foregroundColor(statusColor)
            }
            
            if item.progress.status != "Completed" && item.progress.status != "Failed" && item.progress.status != "Cancelled" {
                ProgressView(value: Double(item.progress.percentage) / 100.0)
                    .frame(height: 4)
                
                // 显示速度和时间
                HStack(spacing: 12) {
                    if let speed = item.progress.speed {
                        Text("速度: \(speed)")
                            .font(.system(size: 10))
                            .foregroundColor(.gray)
                    }
                    
                    if let elapsed = item.progress.elapsedTime {
                        Text("耗时: \(formatTime(elapsed))")
                            .font(.system(size: 10))
                            .foregroundColor(.gray)
                    }
                    
                    Spacer()
                }
                .padding(.top, 4)
            }
        }
        .padding(10)
        .background(Color(nsColor: .controlBackgroundColor))
        .cornerRadius(6)
    }
    
    private func handleCancel() {
        Task {
            do {
                try await APIService.shared.cancelDownload(downloadId: item.downloadId)
                onCancel()
            } catch {
                print("取消下载失败: \(error)")
            }
        }
    }
    
    private func formatTime(_ seconds: Int) -> String {
        let hours = seconds / 3600
        let minutes = (seconds % 3600) / 60
        let secs = seconds % 60
        
        if hours > 0 {
            return String(format: "%d:%02d:%02d", hours, minutes, secs)
        } else if minutes > 0 {
            return String(format: "%d:%02d", minutes, secs)
        } else {
            return String(format: "%ds", secs)
        }
    }
    
    private var statusText: String {
        switch item.progress.status {
        case "Completed": return "完成"
        case "Failed": return item.progress.error ?? "失败"
        case "Cancelled": return "已取消"
        default: return "\(item.progress.percentage)%"
        }
    }
}

// Preview
#if DEBUG
struct ContentView_Previews: PreviewProvider {
    static var previews: some View {
        ContentView()
    }
}
#endif

