mod commands;
mod python;

use commands::download::DownloadState;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .manage(DownloadState::default())
        .invoke_handler(tauri::generate_handler![
            // Analyze
            commands::analyze::analyze_url,
            commands::analyze::analyze_playlist,
            // Download
            commands::download::start_download,
            commands::download::cancel_download,
            // Settings
            commands::settings::load_settings,
            commands::settings::save_settings,
            commands::settings::get_output_dir,
            // Cookies
            commands::cookies::detect_browsers,
            commands::cookies::test_cookies,
            // Updater
            commands::updater::check_ytdlp_update,
            commands::updater::install_ytdlp_update,
            // History
            commands::history::load_history,
            commands::history::add_history_entry,
            commands::history::search_history,
            commands::history::clear_history,
            // System
            commands::system::get_system_info,
            commands::system::send_notification,
            commands::system::open_file_location,
            commands::system::open_folder,
            commands::system::export_logs,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
