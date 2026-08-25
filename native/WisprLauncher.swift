import AppKit
import ApplicationServices
import AVFoundation
import Foundation
import ServiceManagement

enum LoginItemCommand {
    static func runIfRequested() -> Bool {
        guard let argument = CommandLine.arguments.dropFirst().first,
              argument.hasPrefix("--login-item-") else {
            return false
        }

        do {
            switch argument {
            case "--login-item-status":
                print(statusText(SMAppService.mainApp.status))
            case "--login-item-enable":
                try SMAppService.mainApp.register()
                print(statusText(SMAppService.mainApp.status))
            case "--login-item-disable":
                try SMAppService.mainApp.unregister()
                print(statusText(SMAppService.mainApp.status))
            case "--login-item-open-settings":
                SMAppService.openSystemSettingsLoginItems()
                print(statusText(SMAppService.mainApp.status))
            default:
                fputs("Unbekannter Verwaltungsbefehl.\n", stderr)
                exit(2)
            }
        } catch {
            fputs("\(error.localizedDescription)\n", stderr)
            exit(1)
        }
        return true
    }

    private static func statusText(_ status: SMAppService.Status) -> String {
        switch status {
        case .notRegistered:
            return "not-registered"
        case .enabled:
            return "enabled"
        case .requiresApproval:
            return "requires-approval"
        case .notFound:
            return "not-found"
        @unknown default:
            return "unknown"
        }
    }
}

final class WisprAppDelegate: NSObject, NSApplicationDelegate {
    private var pythonProcess: Process?
    private var accessibilityTimer: Timer?

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)

        // Dadurch erscheint Wispr – nicht das gesamte Terminal – in den
        // macOS-Dialogen für Bedienungshilfen und Mikrofon. Python startet
        // erst nach der Freigabe, damit sein Tastatur-Listener nicht in einem
        // dauerhaft unbrauchbaren Zustand endet.
        if AVCaptureDevice.authorizationStatus(for: .audio) == .notDetermined {
            AVCaptureDevice.requestAccess(for: .audio) { _ in }
        }
        waitForAccessibilityAndStart()
    }

    func applicationWillTerminate(_ notification: Notification) {
        accessibilityTimer?.invalidate()
        if let process = pythonProcess, process.isRunning {
            process.terminate()
        }
    }

    private func waitForAccessibilityAndStart() {
        if AXIsProcessTrusted() {
            startPythonApp()
            return
        }

        let axPromptKey = kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String
        _ = AXIsProcessTrustedWithOptions([axPromptKey: true] as CFDictionary)
        accessibilityTimer = Timer.scheduledTimer(withTimeInterval: 0.5, repeats: true) {
            [weak self] timer in
            guard AXIsProcessTrusted() else { return }
            timer.invalidate()
            self?.accessibilityTimer = nil
            self?.startPythonApp()
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
        if LoginItemCommand.runIfRequested() {
            return
        }
        let app = NSApplication.shared
        let delegate = WisprAppDelegate()
        app.delegate = delegate
        app.run()
    }
}
