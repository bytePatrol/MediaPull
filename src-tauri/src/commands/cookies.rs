use tauri::AppHandle;
use crate::python;

#[tauri::command]
pub async fn detect_browsers(app: AppHandle) -> Result<serde_json::Value, String> {
    python::run_python_module(&app, "cookies", &["detect"], None).await
}

#[tauri::command]
pub async fn test_cookies(app: AppHandle, browser: String, profile: String) -> Result<serde_json::Value, String> {
    python::run_python_module(&app, "cookies", &["test", &browser, &profile], None).await
}
