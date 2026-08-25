import AppKit
import ApplicationServices
import AVFoundation
import Foundation

final class WisprAppDelegate: NSObject, NSApplicationDelegate {
    private var pythonProcess: Process?

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)

        // Dadurch erscheint Wispr – nicht das gesamte Terminal – in den
        // macOS-Dialogen für Bedienungshilfen und Mikrofon.
        let axPromptKey = kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String
        _ = AXIsProcessTrustedWithOptions([axPromptKey: true] as CFDictionary)
        if AVCaptureDevice.authorizationStatus(for: .audio) == .notDetermined {
            AVCaptureDevice.requestAccess(for: .audio) { _ in }
        }

        startPythonApp()
    }

    func applicationWillTerminate(_ notification: Notification) {
        if let process = pythonProcess, process.isRunning {
            process.terminate()
        }
    }

    private func startPythonApp() {
        let projectDirectory = Bundle.main.bundleURL
            .deletingLastPathComponent()
            .standardizedFileURL
        let pythonURL = projectDirectory.appendingPathComponent(".venv/bin/python3")
        let scriptURL = projectDirectory.appendingPathComponent("diktieren.py")

        guard FileManager.default.isExecutableFile(atPath: pythonURL.path),
              FileManager.default.fileExists(atPath: scriptURL.path) else {
            showStartupError(
                "Wispr.app muss im Wispr-Projektordner liegen. Bitte führe dort erneut ./setup.sh aus."
            )
            return
        }

        let process = Process()
        process.executableURL = pythonURL
        process.arguments = [scriptURL.path]
        process.currentDirectoryURL = projectDirectory
        process.environment = ProcessInfo.processInfo.environment.merging([
            "WISPR_LAUNCHED_AS_APP": "1"
        ]) { _, newValue in newValue }

        let logURL = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/Logs/Wispr.log")
        FileManager.default.createFile(atPath: logURL.path, contents: nil)
        if let log = try? FileHandle(forWritingTo: logURL) {
            _ = try? log.seekToEnd()
            process.standardOutput = log
            process.standardError = log
        }

        process.terminationHandler = { _ in
            DispatchQueue.main.async {
                NSApp.terminate(nil)
            }
        }

        do {
            try process.run()
            pythonProcess = process
        } catch {
            showStartupError("Python konnte nicht gestartet werden: \(error.localizedDescription)")
        }
    }

    private func showStartupError(_ message: String) {
        NSApp.setActivationPolicy(.regular)
        NSApp.activate(ignoringOtherApps: true)
        let alert = NSAlert()
        alert.messageText = "Wispr konnte nicht starten"
        alert.informativeText = message
        alert.alertStyle = .critical
        alert.runModal()
        NSApp.terminate(nil)
    }
}

@main
struct WisprLauncher {
    static func main() {
        let app = NSApplication.shared
        let delegate = WisprAppDelegate()
        app.delegate = delegate
        app.run()
    }
}
