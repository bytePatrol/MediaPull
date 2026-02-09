use serde::{Deserialize, Serialize};
use std::sync::Arc;
use tauri::{AppHandle, Emitter, State};
use tokio::sync::Mutex;
use crate::python::{self, ProcessHandle, new_process_handle, kill_process, LogPayload};

/// Shared state for the current download process
pub struct DownloadState {
    pub process: ProcessHandle,
    pub is_downloading: Arc<Mutex<bool>>,
}

impl Default for DownloadState {
    fn default() -> Self {
        Self {
            process: new_process_handle(),
            is_downloading: Arc::new(Mutex::new(false)),
        }
    }
}

#[derive(Debug, Serialize, Deserialize)]
pub struct ChapterRequest {
    pub title: String,
    pub start_time: f64,
    pub end_time: f64,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct DownloadRequest {
    pub url: String,
    pub quality: String,
    pub output_dir: String,
    pub audio_only: bool,
    pub sponsorblock: bool,
    pub trim_start: Option<String>,
    pub trim_end: Option<String>,
    pub cookies_browser: Option<String>,
    pub cookies_profile: Option<String>,
    pub bitrate_mode: Option<String>,
    pub custom_bitrate: Option<u32>,
    pub per_resolution: Option<std::collections::HashMap<String, u32>>,
    pub chapters: Option<Vec<ChapterRequest>>,
}

#[tauri::command]
pub async fn start_download(
    app: AppHandle,
    state: State<'_, DownloadState>,
    request: DownloadRequest,
) -> Result<serde_json::Value, String> {
    // Check if already downloading
    {
        let mut downloading = state.is_downloading.lock().await;
        if *downloading {
            return Err("A download is already in progress".to_string());
        }
        *downloading = true;
    }

    let _ = app.emit("download-log", LogPayload {
        level: "info".to_string(),
        message: "Starting download pipeline...".to_string(),
    });

    // Build args for the Python download module
    let mut args: Vec<String> = vec![
        "run".to_string(),
        "--url".to_string(), request.url,
        "--quality".to_string(), request.quality,
        "--output-dir".to_string(), request.output_dir,
    ];

    let has_chapters = request.chapters.as_ref().map_or(false, |c| !c.is_empty());

    if request.audio_only {
        args.push("--audio-only".to_string());
    }
    // Auto-disable SponsorBlock when downloading chapters (segment removal shifts timestamps)
    if request.sponsorblock && !has_chapters {
        args.push("--sponsorblock".to_string());
    }
    if has_chapters {
        if let Ok(json_str) = serde_json::to_string(&request.chapters) {
            args.push("--chapters".to_string());
            args.push(json_str);
        }
    }
    if let Some(ref start) = request.trim_start {
        args.push("--trim-start".to_string());
        args.push(start.clone());
    }
    if let Some(ref end) = request.trim_end {
        args.push("--trim-end".to_string());
        args.push(end.clone());
    }
    if let Some(ref browser) = request.cookies_browser {
        args.push("--cookies-browser".to_string());
        args.push(browser.clone());
    }
    if let Some(ref profile) = request.cookies_profile {
        args.push("--cookies-profile".to_string());
        args.push(profile.clone());
    }
    if let Some(ref mode) = request.bitrate_mode {
        args.push("--bitrate-mode".to_string());
        args.push(mode.clone());
    }
    if let Some(bitrate) = request.custom_bitrate {
        args.push("--custom-bitrate".to_string());
        args.push(bitrate.to_string());
    }
    if let Some(ref per_res) = request.per_resolution {
        // Pass as JSON string
        if let Ok(json_str) = serde_json::to_string(per_res) {
            args.push("--per-res-bitrates".to_string());
            args.push(json_str);
        }
    }

    let arg_refs: Vec<&str> = args.iter().map(|s| s.as_str()).collect();
    let process_handle = state.process.clone();

    let result = python::run_python_module(
        &app,
        "download",
        &arg_refs,
        Some(process_handle),
    ).await;

    // Reset downloading state
    {
        let mut downloading = state.is_downloading.lock().await;
        *downloading = false;
    }

    // Emit completion event
    match &result {
        Ok(data) => {
            let _ = app.emit("download-complete", data.clone());
        }
        Err(e) => {
            let _ = app.emit("download-error", e.clone());
        }
    }

    result
}

#[tauri::command]
pub async fn cancel_download(
    app: AppHandle,
    state: State<'_, DownloadState>,
) -> Result<(), String> {
    kill_process(&state.process).await;
    let mut downloading = state.is_downloading.lock().await;
    *downloading = false;
    let _ = app.emit("download-log", LogPayload {
        level: "warning".to_string(),
        message: "Download cancelled by user".to_string(),
    });
    let _ = app.emit("download-cancelled", ());
    Ok(())
}
