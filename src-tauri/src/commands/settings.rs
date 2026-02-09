use tauri::AppHandle;
use crate::python;

#[tauri::command]
pub async fn load_settings(app: AppHandle) -> Result<serde_json::Value, String> {
    python::run_python_module(&app, "settings", &["load"], None).await
}

#[tauri::command]
pub async fn save_settings(app: AppHandle, settings: serde_json::Value) -> Result<serde_json::Value, String> {
    let settings_str = serde_json::to_string(&settings).map_err(|e| e.to_string())?;
    python::run_python_module(&app, "settings", &["save", &settings_str], None).await
}

#[tauri::command]
pub async fn get_output_dir(app: AppHandle) -> Result<serde_json::Value, String> {
    python::run_python_module(&app, "settings", &["get-output-dir"], None).await
}
