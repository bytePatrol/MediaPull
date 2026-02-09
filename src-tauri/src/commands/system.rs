use tauri::AppHandle;
use tauri_plugin_dialog::DialogExt;
use crate::python;

#[tauri::command]
pub async fn get_system_info(app: AppHandle) -> Result<serde_json::Value, String> {
    python::run_python_module(&app, "sysmon", &["snapshot"], None).await
}

#[tauri::command]
pub async fn send_notification(app: AppHandle, title: String, message: String) -> Result<serde_json::Value, String> {
    python::run_python_module(&app, "notify", &[&title, &message], None).await
}

#[tauri::command]
pub async fn open_file_location(path: String) -> Result<(), String> {
    std::process::Command::new("open")
        .arg("-R")
        .arg(&path)
        .spawn()
        .map_err(|e| format!("Failed to open file location: {}", e))?;
    Ok(())
}

#[tauri::command]
pub async fn open_folder(path: String) -> Result<(), String> {
    std::process::Command::new("open")
        .arg(&path)
        .spawn()
        .map_err(|e| format!("Failed to open folder: {}", e))?;
    Ok(())
}

#[tauri::command]
pub async fn export_logs(app: AppHandle, content: String) -> Result<String, String> {
    let (tx, rx) = tokio::sync::oneshot::channel();

    app.dialog()
        .file()
        .set_file_name("media-pull-logs.txt")
        .add_filter("Text files", &["txt"])
        .save_file(move |path| {
            let _ = tx.send(path);
        });

    let path = rx.await.map_err(|_| "Dialog cancelled".to_string())?;

    match path {
        Some(file_path) => {
            let p = file_path.as_path().ok_or("Invalid file path")?;
            std::fs::write(p, &content)
                .map_err(|e| format!("Failed to write file: {}", e))?;
            Ok(p.to_string_lossy().to_string())
        }
        None => Err("Export cancelled".to_string()),
    }
}
