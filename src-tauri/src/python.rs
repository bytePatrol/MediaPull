use serde::{Deserialize, Serialize};
use std::io::{BufRead, BufReader, Read};
use std::process::{Child, Command, Stdio};
use std::sync::Arc;
use tauri::{AppHandle, Emitter, Manager};
use tokio::sync::Mutex;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PythonEvent {
    pub event: String,
    #[serde(default)]
    pub stage: Option<String>,
    #[serde(default)]
    pub percent: Option<f64>,
    #[serde(default)]
    pub speed_mbps: Option<f64>,
    #[serde(default)]
    pub eta_seconds: Option<f64>,
    #[serde(default)]
    pub fps: Option<f64>,
    #[serde(default)]
    pub level: Option<String>,
    #[serde(default)]
    pub message: Option<String>,
    #[serde(default)]
    pub code: Option<String>,
    #[serde(default)]
    pub data: Option<serde_json::Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProgressPayload {
    pub stage: String,
    pub percent: f64,
    pub speed_mbps: f64,
    pub eta_seconds: f64,
    pub fps: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LogPayload {
    pub level: String,
    pub message: String,
}

/// Get the path to the Python scripts directory.
/// In production, scripts are bundled as resources at Contents/Resources/python.
/// In development, look relative to the executable or project root.
pub fn get_python_dir(app: &AppHandle) -> String {
    // 1. Bundled resources (production)
    if let Ok(resource_dir) = app.path().resource_dir() {
        let resource_path: std::path::PathBuf = resource_dir;
        let bundled = resource_path.join("python");
        if bundled.exists() && bundled.is_dir() {
            return bundled.to_string_lossy().to_string();
        }
        // Tauri may nest under _up_ for relative paths
        let up_bundled = resource_path.join("_up_").join("python");
        if up_bundled.exists() && up_bundled.is_dir() {
            return up_bundled.to_string_lossy().to_string();
        }
    }

    // 2. Development: look relative to the executable
    if let Ok(exe) = std::env::current_exe() {
        // exe is typically in src-tauri/target/debug/media-pull
        // python/ is at the project root (3 levels up from target/debug/)
        if let Some(project_root) = exe.parent()
            .and_then(|p| p.parent())
            .and_then(|p| p.parent())
            .and_then(|p| p.parent())
        {
            let dev_path = project_root.join("python");
            if dev_path.exists() && dev_path.is_dir() {
                return dev_path.to_string_lossy().to_string();
            }
        }
    }

    // 3. Relative to current working directory
    if let Ok(cwd) = std::env::current_dir() {
        let cwd_path = cwd.join("python");
        if cwd_path.exists() && cwd_path.is_dir() {
            return cwd_path.to_string_lossy().to_string();
        }
    }

    "python".to_string()
}

/// Resolve which python3 to use
fn find_python() -> String {
    for path in &[
        "/opt/homebrew/bin/python3",
        "/usr/local/bin/python3",
        "/usr/bin/python3",
    ] {
        if std::path::Path::new(path).exists() {
            return path.to_string();
        }
    }
    "python3".to_string()
}

/// Shared handle to a running Python child process for cancellation
pub type ProcessHandle = Arc<Mutex<Option<Child>>>;

pub fn new_process_handle() -> ProcessHandle {
    Arc::new(Mutex::new(None))
}

/// Spawn a Python module and stream JSON line events back.
/// Returns the final `result` data or an error.
pub async fn run_python_module(
    app: &AppHandle,
    module: &str,
    args: &[&str],
    process_handle: Option<ProcessHandle>,
) -> Result<serde_json::Value, String> {
    let python = find_python();
    let python_dir = get_python_dir(app);

    // PYTHONPATH must point to the parent of the python/ package directory
    let python_parent = std::path::Path::new(&python_dir)
        .parent()
        .map(|p| p.to_string_lossy().to_string())
        .unwrap_or_else(|| ".".to_string());

    // Log what we're doing for debugging
    let _ = app.emit("download-log", LogPayload {
        level: "debug".to_string(),
        message: format!("Python: {} -m python.{} | PYTHONPATH={}", python, module, python_parent),
    });

    let mut cmd = Command::new(&python);
    cmd.arg("-m")
        .arg(format!("python.{}", module))
        .args(args)
        .env("PYTHONPATH", &python_parent)
        .env("PYTHONIOENCODING", "utf-8")
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());

    let mut child = cmd.spawn().map_err(|e| format!("Failed to spawn Python: {}", e))?;

    let stdout = child.stdout.take().ok_or("Failed to capture stdout")?;
    let stderr = child.stderr.take().ok_or("Failed to capture stderr")?;

    // Read stderr in a background thread to avoid deadlock
    let stderr_thread = std::thread::spawn(move || {
        let mut stderr_output = String::new();
        let mut reader = BufReader::new(stderr);
        let _ = reader.read_to_string(&mut stderr_output);
        stderr_output
    });

    // Store child for cancellation if a handle was provided
    if let Some(ref handle) = process_handle {
        let mut guard = handle.lock().await;
        *guard = Some(child);
    }

    let reader = BufReader::new(stdout);
    let mut result: Option<serde_json::Value> = None;
    let mut error_msg: Option<String> = None;
    let mut error_code: Option<String> = None;

    let app_clone = app.clone();

    for line in reader.lines() {
        let line = match line {
            Ok(l) => l,
            Err(_) => continue,
        };

        if line.trim().is_empty() {
            continue;
        }

        let event: PythonEvent = match serde_json::from_str(&line) {
            Ok(e) => e,
            Err(_) => {
                let _ = app_clone.emit("download-log", LogPayload {
                    level: "debug".to_string(),
                    message: line,
                });
                continue;
            }
        };

        match event.event.as_str() {
            "progress" => {
                let _ = app_clone.emit("download-progress", ProgressPayload {
                    stage: event.stage.unwrap_or_default(),
                    percent: event.percent.unwrap_or(0.0),
                    speed_mbps: event.speed_mbps.unwrap_or(0.0),
                    eta_seconds: event.eta_seconds.unwrap_or(0.0),
                    fps: event.fps.unwrap_or(0.0),
                });
            }
            "log" => {
                let _ = app_clone.emit("download-log", LogPayload {
                    level: event.level.unwrap_or_else(|| "info".to_string()),
                    message: event.message.unwrap_or_default(),
                });
            }
            "result" => {
                result = event.data;
            }
            "error" => {
                error_code = event.code;
                error_msg = event.message;
            }
            _ => {}
        }
    }

    // Wait for the process to finish
    if let Some(ref handle) = process_handle {
        let mut guard = handle.lock().await;
        if let Some(ref mut child) = *guard {
            let _ = child.wait();
        }
        *guard = None;
    }

    // Collect stderr
    let stderr_output = stderr_thread.join().unwrap_or_default();
    if !stderr_output.is_empty() {
        // Log any stderr output (may contain Python tracebacks)
        for line in stderr_output.lines().take(20) {
            let line = line.trim();
            if !line.is_empty() {
                let _ = app.emit("download-log", LogPayload {
                    level: "debug".to_string(),
                    message: format!("[stderr] {}", line),
                });
            }
        }
    }

    if let Some(msg) = error_msg {
        let code = error_code.unwrap_or_else(|| "unknown".to_string());
        Err(format!("{}: {}", code, msg))
    } else if let Some(data) = result {
        Ok(data)
    } else {
        // No result event — include stderr in the error message for debugging
        let stderr_summary = stderr_output.lines()
            .filter(|l| !l.trim().is_empty())
            .collect::<Vec<_>>()
            .join(" | ");
        if stderr_summary.is_empty() {
            Err(format!("Python module '{}' returned no result (PYTHONPATH={})", module, python_parent))
        } else {
            Err(format!("Python error: {}", stderr_summary))
        }
    }
}

/// Kill a running Python process
pub async fn kill_process(handle: &ProcessHandle) {
    let mut guard = handle.lock().await;
    if let Some(ref mut child) = *guard {
        let _ = child.kill();
        let _ = child.wait();
    }
    *guard = None;
}
