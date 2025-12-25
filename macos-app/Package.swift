// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "ZhihuDownloader",
    platforms: [
        .macOS(.v13)
    ],
    dependencies: [],
    targets: [
        .executableTarget(
            name: "ZhihuDownloader",
            dependencies: [],
            path: "Sources"
        )
    ]
)

