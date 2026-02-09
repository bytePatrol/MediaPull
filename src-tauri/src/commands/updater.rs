use tauri::AppHandle;
use crate::python;

#[tauri::command]
pub async fn check_ytdlp_update(app: AppHandle) -> Result<serde_json::Value, String> {
    python::run_python_module(&app, "updater", &["check"], None).await
}

#[tauri::command]
pub async fn install_ytdlp_update(app: AppHandle, version: String, nightly: bool) -> Result<serde_json::Value, String> {
    let nightly_str = if nightly { "true" } else { "false" };
    python::run_python_module(&app, "updater", &["install", &version, nightly_str], None).await
}
