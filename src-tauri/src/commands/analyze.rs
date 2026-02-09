use tauri::AppHandle;
use crate::python;

#[tauri::command]
pub async fn analyze_url(app: AppHandle, url: String) -> Result<serde_json::Value, String> {
    python::run_python_module(&app, "analyze", &["video", &url], None).await
}

#[tauri::command]
pub async fn analyze_playlist(app: AppHandle, url: String) -> Result<serde_json::Value, String> {
    python::run_python_module(&app, "analyze", &["playlist", &url], None).await
}
