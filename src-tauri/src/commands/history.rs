use tauri::AppHandle;
use crate::python;

#[tauri::command]
pub async fn load_history(app: AppHandle) -> Result<serde_json::Value, String> {
    python::run_python_module(&app, "history", &["load"], None).await
}

#[tauri::command]
pub async fn add_history_entry(app: AppHandle, entry: serde_json::Value) -> Result<serde_json::Value, String> {
    let entry_str = serde_json::to_string(&entry).map_err(|e| e.to_string())?;
    python::run_python_module(&app, "history", &["add", &entry_str], None).await
}

#[tauri::command]
pub async fn search_history(app: AppHandle, query: String) -> Result<serde_json::Value, String> {
    python::run_python_module(&app, "history", &["search", &query], None).await
}

#[tauri::command]
pub async fn clear_history(app: AppHandle) -> Result<serde_json::Value, String> {
    python::run_python_module(&app, "history", &["clear"], None).await
}
