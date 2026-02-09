/**
 * Media Pull — Main Frontend Module
 *
 * Connects Tauri invoke()/listen() to UI components.
 */

import { initNav, switchPage } from './components/nav.js';
import { initQualityGrid, renderQualityGrid, getSelectedQuality } from './components/quality-grid.js';
import { showProgress, hideProgress, updateProgress, resetProgress } from './components/progress.js';
import { showVideoInfo, hideVideoInfo, getVideoInfo } from './components/video-info.js';
import { initToggles, getOptions, resetTrim } from './components/toggles.js';

// Tauri API — available via withGlobalTauri
const { invoke } = window.__TAURI__.core;
const { listen } = window.__TAURI__.event;

// ============ State ============
let isAnalyzing = false;
let isDownloading = false;
let appSettings = {};
let appConfig = {};
let logEntries = [];
let playlistData = null;
let isPlaylistDownloading = false;
let playlistCancelled = false;

// ============ Init ============
async function init() {
  initNav();
  initToggles();
  initQualityGrid(onQualityChange);
  initSettingsTabs();
  initChapterModal();
  initUpdateModal();
  initPlaylistControls();

  // Event listeners
  document.getElementById('btn-paste').addEventListener('click', pasteUrl);
  document.getElementById('btn-analyze').addEventListener('click', analyzeUrl);
  document.getElementById('btn-download').addEventListener('click', toggleDownload);
  document.getElementById('url-input').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') analyzeUrl();
  });
  document.getElementById('btn-clear-logs').addEventListener('click', clearLogs);
  document.getElementById('btn-export-logs').addEventListener('click', exportLogs);

  // Library (history)
  document.getElementById('btn-clear-history').addEventListener('click', clearHistory);
  document.getElementById('library-search').addEventListener('input', searchHistory);

  // Settings
  document.getElementById('btn-test-cookies').addEventListener('click', testCookies);
  document.getElementById('btn-update-ytdlp').addEventListener('click', checkYtdlpUpdate);
  document.getElementById('btn-refresh-browsers').addEventListener('click', detectBrowsers);
  document.getElementById('settings-cookies-browser').addEventListener('change', populateProfiles);
  document.getElementById('settings-cookies-profile').addEventListener('change', checkProfileWarning);
  initBurnerGuide();

  // Tauri event listeners
  await listen('download-progress', (event) => {
    const { stage, percent, speed_mbps, eta_seconds, fps } = event.payload;
    updateProgress(stage, percent, speed_mbps, eta_seconds, fps);
  });

  await listen('download-log', (event) => {
    const { level, message } = event.payload;
    addLog(level, message);
  });

  await listen('download-complete', (event) => {
    onDownloadComplete(event.payload);
  });

  await listen('download-error', (event) => {
    onDownloadError(typeof event.payload === 'string' ? event.payload : event.payload?.message || 'Unknown error');
  });

  await listen('download-cancelled', () => {
    onDownloadCancelled();
  });

  // Keyboard shortcuts
  document.addEventListener('keydown', (e) => {
    if (e.metaKey && e.key === 'v') {
      // Cmd+V: paste URL
      // Allow default paste into focused input
      if (document.activeElement !== document.getElementById('url-input')) {
        e.preventDefault();
        pasteUrl();
      }
    }
    if (e.metaKey && e.key === 'Enter') {
      e.preventDefault();
      if (isDownloading) return;
      if (getVideoInfo()) {
        toggleDownload();
      } else {
        analyzeUrl();
      }
    }
  });

  // Load settings
  loadSettings();

  // Load history
  loadHistory();

  // Detect browsers for cookie settings
  detectBrowsers();

  // Check for yt-dlp updates on startup
  checkYtdlpUpdate();
}

// ============ URL / Analyze ============
async function pasteUrl() {
  try {
    const text = await navigator.clipboard.readText();
    if (text && (text.includes('youtube.com') || text.includes('youtu.be'))) {
      document.getElementById('url-input').value = text.trim();
    }
  } catch (e) {
    // Clipboard API may not be available
    document.getElementById('url-input').focus();
  }
}

function isPlaylistUrl(url) {
  try {
    const u = new URL(url);
    // /playlist path with list= param
    if (u.pathname === '/playlist' && u.searchParams.has('list')) return true;
    // list= param without v= (pure playlist link, not a video within a playlist)
    if (u.searchParams.has('list') && !u.searchParams.has('v')) {
      // Exclude YouTube Mix playlists (RD prefix)
      const listId = u.searchParams.get('list');
      if (listId.startsWith('RD')) return false;
      return true;
    }
    return false;
  } catch {
    return false;
  }
}

async function analyzeUrl() {
  const url = document.getElementById('url-input').value.trim();
  if (!url) return;

  if (isAnalyzing) return;
  isAnalyzing = true;

  // Reset UI
  hideVideoInfo();
  hideProgress();
  hideDownloadUI();
  hidePlaylistUI();
  resetTrim();

  // Show analyzing state
  document.getElementById('analyzing-indicator').classList.add('visible');
  document.getElementById('btn-analyze').disabled = true;

  addLog('info', `Analyzing: ${url}`);

  try {
    if (isPlaylistUrl(url)) {
      addLog('info', 'Detected playlist URL, fetching playlist info...');
      const result = await invoke('analyze_playlist', { url });
      showPlaylistResult(result);
    } else {
      const result = await invoke('analyze_url', { url });
      showAnalysisResult(result);
    }
  } catch (error) {
    addLog('error', `Analysis failed: ${error}`);
    hideAnalyzing();
  }

  isAnalyzing = false;
}

function showAnalysisResult(info) {
  hideAnalyzing();

  if (!info) {
    addLog('error', 'No video information returned');
    return;
  }

  showVideoInfo(info);

  // Render quality grid
  if (info.formats && info.formats.length > 0) {
    renderQualityGrid(info.formats);
    document.getElementById('quality-section').classList.add('visible');
    document.getElementById('options-row').classList.add('visible');
    document.getElementById('download-section').classList.add('visible');
  }

  addLog('info', `Found: ${info.title}`);
}

function hideAnalyzing() {
  document.getElementById('analyzing-indicator').classList.remove('visible');
  document.getElementById('btn-analyze').disabled = false;
}

// ============ Quality ============
function onQualityChange(quality) {
  const label = document.getElementById('download-label');
  const isAudio = quality === 'audio';

  const labels = {
    2160: 'Download 4K',
    1440: 'Download 1440p',
    1080: 'Download 1080p',
    720: 'Download 720p',
    480: 'Download 480p',
    'audio': 'Download Audio',
  };

  label.textContent = labels[quality] || `Download ${quality}`;
}

// ============ Download ============
async function toggleDownload() {
  if (isDownloading) {
    // Cancel
    if (isPlaylistDownloading) {
      playlistCancelled = true;
      addLog('info', 'Cancelling playlist download after current video...');
    }
    try {
      await invoke('cancel_download');
    } catch (e) {
      addLog('error', `Cancel failed: ${e}`);
    }
    return;
  }

  // Playlist download mode
  if (playlistData) {
    startPlaylistDownload();
    return;
  }

  const info = getVideoInfo();
  if (!info) return;

  const quality = getSelectedQuality();
  if (!quality) return;

  const options = getOptions();

  isDownloading = true;
  updateDownloadButton(true);
  resetProgress();
  showProgress();

  const qualityStr = quality === 'audio' ? 'audio' :
    quality === 2160 ? '4k' : `${quality}p`;

  try {
    const outputDir = appConfig.output_dir || `${window.__TAURI__?.path?.homeDir || '~'}/Downloads`;

    const bitrateSettings = getBitrateSettings();

    await invoke('start_download', {
      request: {
        url: info.url || document.getElementById('url-input').value.trim(),
        quality: qualityStr,
        output_dir: outputDir,
        audio_only: quality === 'audio',
        sponsorblock: options.sponsorblock,
        trim_start: options.trimStart || null,
        trim_end: options.trimEnd || null,
        cookies_browser: appSettings.cookies?.enabled ? appSettings.cookies?.browser : null,
        cookies_profile: appSettings.cookies?.enabled ? appSettings.cookies?.profile : null,
        bitrate_mode: bitrateSettings.mode,
        custom_bitrate: bitrateSettings.custom_bitrate || null,
        per_resolution: bitrateSettings.per_resolution || null,
        chapters: null,
      }
    });
  } catch (error) {
    onDownloadError(typeof error === 'string' ? error : error.message || 'Download failed');
  }
}

async function startChapterDownload(chapters) {
  const info = getVideoInfo();
  if (!info) return;

  const quality = getSelectedQuality();
  if (!quality) return;

  const options = getOptions();

  // Notify SponsorBlock auto-disable
  if (options.sponsorblock) {
    addLog('info', 'SponsorBlock auto-disabled for chapter downloads (segment removal shifts timestamps)');
  }

  isDownloading = true;
  updateDownloadButton(true);
  resetProgress();
  showProgress();

  addLog('info', `Downloading ${chapters.length} chapters...`);

  const qualityStr = quality === 'audio' ? 'audio' :
    quality === 2160 ? '4k' : `${quality}p`;

  try {
    const outputDir = appConfig.output_dir || `${window.__TAURI__?.path?.homeDir || '~'}/Downloads`;
    const bitrateSettings = getBitrateSettings();

    await invoke('start_download', {
      request: {
        url: info.url || document.getElementById('url-input').value.trim(),
        quality: qualityStr,
        output_dir: outputDir,
        audio_only: quality === 'audio',
        sponsorblock: options.sponsorblock,
        trim_start: null,
        trim_end: null,
        cookies_browser: appSettings.cookies?.enabled ? appSettings.cookies?.browser : null,
        cookies_profile: appSettings.cookies?.enabled ? appSettings.cookies?.profile : null,
        bitrate_mode: bitrateSettings.mode,
        custom_bitrate: bitrateSettings.custom_bitrate || null,
        per_resolution: bitrateSettings.per_resolution || null,
        chapters: chapters,
      }
    });
  } catch (error) {
    onDownloadError(typeof error === 'string' ? error : error.message || 'Download failed');
  }
}

function onDownloadComplete(data) {
  if (isPlaylistDownloading) return; // Playlist loop handles its own completion

  isDownloading = false;
  updateDownloadButton(false);
  updateProgress('complete', 100, 0, 0, 0);

  const isChapterDl = data?.chapter_count > 0;
  const message = isChapterDl
    ? `Chapter download complete: ${data.chapter_count} files`
    : `Download complete: ${data?.title || 'video'}`;
  addLog('info', message);

  // Add to history
  const info = getVideoInfo();
  if (info) {
    addHistoryEntry({
      title: info.title,
      url: info.url,
      channel: info.channel,
      quality: getSelectedQuality()?.toString() || '',
      output_path: data?.output_path || data?.output_files?.[0] || '',
      file_size: data?.size || 0,
    });
  }

  // Send notification
  invoke('send_notification', {
    title: isChapterDl ? 'Chapter Download Complete' : 'Download Complete',
    message: isChapterDl ? `${data.chapter_count} chapters saved` : (data?.title || 'Video downloaded successfully'),
  }).catch(() => {});
}

function onDownloadError(error) {
  if (isPlaylistDownloading) return; // Playlist loop handles errors
  isDownloading = false;
  updateDownloadButton(false);
  hideProgress();
  addLog('error', `Download failed: ${error}`);
}

function onDownloadCancelled() {
  if (isPlaylistDownloading) {
    playlistCancelled = true;
    return; // Playlist loop will detect cancellation
  }
  isDownloading = false;
  updateDownloadButton(false);
  hideProgress();
  addLog('warning', 'Download cancelled');
}

function updateDownloadButton(downloading) {
  const btn = document.getElementById('btn-download');
  const label = document.getElementById('download-label');

  if (downloading) {
    btn.classList.add('downloading');
    label.textContent = 'Cancel Download';
  } else {
    btn.classList.remove('downloading');
    // Restore quality label
    const q = getSelectedQuality();
    if (q) onQualityChange(q);
  }
}

function hideDownloadUI() {
  document.getElementById('quality-section').classList.remove('visible');
  document.getElementById('options-row').classList.remove('visible');
  document.getElementById('download-section').classList.remove('visible');
  document.getElementById('playlist-section').classList.remove('visible');
  hideProgress();
}

// ============ Playlist ============
function initPlaylistControls() {
  document.getElementById('playlist-select-all').addEventListener('click', () => {
    document.querySelectorAll('#playlist-list .playlist-item:not(.unavailable) input[type=checkbox]').forEach(cb => {
      cb.checked = true;
      cb.closest('.playlist-item').classList.add('selected');
    });
  });

  document.getElementById('playlist-select-none').addEventListener('click', () => {
    document.querySelectorAll('#playlist-list .playlist-item input[type=checkbox]').forEach(cb => {
      cb.checked = false;
      cb.closest('.playlist-item').classList.remove('selected');
    });
  });
}

function showPlaylistResult(result) {
  hideAnalyzing();

  if (!result || !result.items || result.items.length === 0) {
    addLog('error', 'No playlist items found');
    return;
  }

  playlistData = result;

  // Show playlist heading
  document.getElementById('playlist-heading').textContent = result.playlist_title || 'Playlist';
  const available = result.items.filter(i => i.is_available).length;
  document.getElementById('playlist-subtitle').textContent =
    `${available} video${available !== 1 ? 's' : ''} available`;

  renderPlaylistItems(result.items);
  document.getElementById('playlist-section').classList.add('visible');

  // Show quality grid with generic presets (no format data)
  renderQualityGrid(null);
  document.getElementById('quality-section').classList.add('visible');
  document.getElementById('options-row').classList.add('visible');
  document.getElementById('download-section').classList.add('visible');

  addLog('info', `Playlist: ${result.playlist_title} (${result.items.length} videos)`);
}

function renderPlaylistItems(items) {
  const list = document.getElementById('playlist-list');
  list.innerHTML = '';

  for (const item of items) {
    const el = document.createElement('div');
    el.className = `playlist-item${item.is_available ? ' selected' : ' unavailable'}`;
    el.dataset.url = item.url || '';
    el.dataset.title = item.title || '';
    el.dataset.id = item.id || '';

    const durStr = item.duration > 0 ? formatDuration(item.duration) : '';
    const metaParts = [item.channel, durStr].filter(Boolean).join(' \u00b7 ');

    el.innerHTML = `
      <input type="checkbox" ${item.is_available ? 'checked' : 'disabled'}>
      <span class="playlist-item-index">${item.index}</span>
      <div class="playlist-item-info">
        <div class="playlist-item-title">${escapeHtml(item.title)}</div>
        <div class="playlist-item-meta">${escapeHtml(metaParts)}</div>
      </div>
    `;

    const cb = el.querySelector('input[type=checkbox]');
    cb.addEventListener('change', () => {
      el.classList.toggle('selected', cb.checked);
    });
    el.addEventListener('click', (e) => {
      if (e.target.tagName === 'INPUT') return;
      if (!item.is_available) return;
      cb.checked = !cb.checked;
      el.classList.toggle('selected', cb.checked);
    });

    list.appendChild(el);
  }
}

function hidePlaylistUI() {
  document.getElementById('playlist-section').classList.remove('visible');
  playlistData = null;
}

async function startPlaylistDownload() {
  const selectedItems = [];
  document.querySelectorAll('#playlist-list .playlist-item').forEach(el => {
    const cb = el.querySelector('input[type=checkbox]');
    if (cb?.checked) {
      selectedItems.push({
        url: el.dataset.url,
        title: el.dataset.title,
        id: el.dataset.id,
      });
    }
  });

  if (selectedItems.length === 0) {
    addLog('warning', 'No videos selected');
    return;
  }

  isDownloading = true;
  isPlaylistDownloading = true;
  playlistCancelled = false;
  updateDownloadButton(true);
  resetProgress();
  showProgress();

  const quality = getSelectedQuality();
  const qualityStr = quality === 'audio' ? 'audio' :
    quality === 2160 ? '4k' : `${quality}p`;
  const options = getOptions();
  const baseDir = appConfig.output_dir || `${window.__TAURI__?.path?.homeDir || '~'}/Downloads`;
  const playlistFolder = sanitizeFilename(playlistData?.playlist_title || 'Playlist');
  const outputDir = `${baseDir}/${playlistFolder}`;
  const bitrateSettings = getBitrateSettings();

  let successCount = 0;
  let failCount = 0;
  const total = selectedItems.length;

  addLog('info', `Starting playlist download: ${total} videos at ${qualityStr}`);

  for (let i = 0; i < total; i++) {
    if (playlistCancelled) {
      addLog('warning', `Playlist download cancelled. ${successCount} completed, ${total - i} skipped.`);
      break;
    }

    const item = selectedItems[i];
    addLog('info', `[${i + 1}/${total}] Downloading: ${item.title}`);

    try {
      await invoke('start_download', {
        request: {
          url: item.url,
          quality: qualityStr,
          output_dir: outputDir,
          audio_only: quality === 'audio',
          sponsorblock: options.sponsorblock,
          trim_start: null,
          trim_end: null,
          cookies_browser: appSettings.cookies?.enabled ? appSettings.cookies?.browser : null,
          cookies_profile: appSettings.cookies?.enabled ? appSettings.cookies?.profile : null,
          bitrate_mode: bitrateSettings.mode,
          custom_bitrate: bitrateSettings.custom_bitrate || null,
          per_resolution: bitrateSettings.per_resolution || null,
          chapters: null,
        }
      });
      successCount++;
      addLog('info', `[${i + 1}/${total}] Complete: ${item.title}`);
    } catch (error) {
      failCount++;
      const msg = typeof error === 'string' ? error : error?.message || 'Unknown error';
      addLog('error', `[${i + 1}/${total}] Failed: ${item.title} — ${msg}`);
    }
  }

  // Playlist download finished
  isDownloading = false;
  isPlaylistDownloading = false;
  playlistCancelled = false;
  updateDownloadButton(false);

  if (successCount > 0) {
    updateProgress('complete', 100, 0, 0, 0);
  } else {
    hideProgress();
  }

  const summary = `Playlist download complete: ${successCount} succeeded, ${failCount} failed`;
  addLog('info', summary);

  invoke('send_notification', {
    title: 'Playlist Download Complete',
    message: `${successCount}/${total} videos downloaded`,
  }).catch(() => {});
}

function sanitizeFilename(name) {
  return name
    .replace(/[\/\\:*?"<>|]/g, '_')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 200) || 'Playlist';
}

function formatDuration(seconds) {
  if (!seconds || seconds <= 0) return '';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  return `${m}:${String(s).padStart(2, '0')}`;
}

// ============ Logging ============
function addLog(level, message) {
  const time = new Date().toLocaleTimeString('en-US', { hour12: false });
  logEntries.push({ time, level, message });

  // Update log container
  const container = document.getElementById('log-container');
  const entry = document.createElement('div');
  entry.className = `log-entry ${level}`;
  entry.innerHTML = `<span class="log-time">${time}</span>${escapeHtml(message)}`;
  container.appendChild(entry);
  container.scrollTop = container.scrollHeight;

  // Keep max 1000 entries
  if (logEntries.length > 1000) {
    logEntries.shift();
    container.firstChild?.remove();
  }
}

function clearLogs() {
  logEntries = [];
  document.getElementById('log-container').innerHTML = '';
}

async function exportLogs() {
  if (logEntries.length === 0) {
    addLog('info', 'No logs to export');
    return;
  }

  const content = logEntries
    .map(e => `[${e.time}] [${e.level.toUpperCase()}] ${e.message}`)
    .join('\n');

  try {
    const path = await invoke('export_logs', { content });
    addLog('info', `Logs exported to ${path}`);
  } catch (e) {
    if (!String(e).includes('cancelled')) {
      addLog('error', `Export failed: ${e}`);
    }
  }
}

// ============ History ============
async function loadHistory() {
  try {
    const result = await invoke('load_history');
    renderHistory(result.entries || []);
  } catch {
    // History not available yet
  }
}

async function addHistoryEntry(entry) {
  try {
    await invoke('add_history_entry', { entry });
    loadHistory();
  } catch (e) {
    addLog('debug', `Failed to save history: ${e}`);
  }
}

async function searchHistory() {
  const query = document.getElementById('library-search').value.trim();
  if (!query) {
    loadHistory();
    return;
  }
  try {
    const result = await invoke('search_history', { query });
    renderHistory(result.entries || []);
  } catch {
    // ignore
  }
}

async function clearHistory() {
  try {
    await invoke('clear_history');
    renderHistory([]);
  } catch (e) {
    addLog('error', `Failed to clear history: ${e}`);
  }
}

function renderHistory(entries) {
  const list = document.getElementById('library-list');
  const empty = document.getElementById('library-empty');

  // Clear existing items (keep empty state)
  list.querySelectorAll('.history-item').forEach(el => el.remove());

  if (entries.length === 0) {
    empty.style.display = '';
    return;
  }

  empty.style.display = 'none';

  for (const entry of entries) {
    const item = document.createElement('div');
    item.className = 'history-item';
    item.innerHTML = `
      <div class="history-item-title">${escapeHtml(entry.title || 'Unknown')}</div>
      <div class="history-item-meta">${entry.quality || ''}</div>
      <div class="history-item-meta">${formatDate(entry.timestamp)}</div>
    `;
    item.addEventListener('click', () => {
      if (entry.url) {
        document.getElementById('url-input').value = entry.url;
        switchPage('downloader');
      }
    });
    list.appendChild(item);
  }
}

// ============ Settings ============
function initSettingsTabs() {
  document.querySelectorAll('.settings-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.settings-tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');

      document.querySelectorAll('.settings-tab-content').forEach(c => c.classList.remove('active'));
      const target = document.getElementById(`tab-${tab.dataset.tab}`);
      if (target) target.classList.add('active');
    });
  });

  // Bitrate mode tabs
  initBitrateMode();

  // SponsorBlock categories
  const sbCats = [
    { id: 'sponsor',         label: 'Sponsor',          desc: 'Paid promotions & ads',           color: '#00D16B', icon: 'M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5' },
    { id: 'intro',           label: 'Intro',            desc: 'Intro animation / bumper',        color: '#00CED1', icon: 'M5 3l14 9-14 9V3z' },
    { id: 'outro',           label: 'Outro',            desc: 'End cards & credits',             color: '#1E90FF', icon: 'M18 6L6 18M6 6l12 12' },
    { id: 'selfpromo',       label: 'Self-Promo',       desc: 'Creator merch & channel plugs',   color: '#FFD700', icon: 'M12 2a10 10 0 100 20 10 10 0 000-20zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z' },
    { id: 'preview',         label: 'Preview',          desc: 'Recap or upcoming preview',       color: '#FF8C00', icon: 'M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8zm11 4a4 4 0 100-8 4 4 0 000 8z' },
    { id: 'music_offtopic',  label: 'Off-Topic Music',  desc: 'Non-music in music videos',       color: '#DA70D6', icon: 'M9 18V5l12-2v13M9 18a3 3 0 11-6 0 3 3 0 016 0zm12-2a3 3 0 11-6 0 3 3 0 016 0z' },
    { id: 'interaction',     label: 'Interaction',      desc: '"Like & subscribe" reminders',     color: '#FF6B6B', icon: 'M14 9V5a3 3 0 00-6 0v4H5a2 2 0 00-2 2v7a2 2 0 002 2h14a2 2 0 002-2v-7a2 2 0 00-2-2h-5z' },
    { id: 'filler',          label: 'Filler',           desc: 'Tangents & off-topic padding',    color: '#A0A0A0', icon: 'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z' },
  ];
  const container = document.getElementById('sb-categories');
  for (const cat of sbCats) {
    const card = document.createElement('label');
    card.className = 'sb-cat-card active';
    card.style.setProperty('--cat-color', cat.color);
    card.innerHTML = `
      <input type="checkbox" checked data-sb-cat="${cat.id}" class="sb-cat-input">
      <div class="sb-cat-indicator">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="${cat.icon}"/></svg>
      </div>
      <div class="sb-cat-text">
        <div class="sb-cat-label">${cat.label}</div>
        <div class="sb-cat-desc">${cat.desc}</div>
      </div>
      <div class="sb-cat-check">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
      </div>
    `;
    const input = card.querySelector('input');
    input.addEventListener('change', () => {
      card.classList.toggle('active', input.checked);
      updateSbToggleAllBtn();
    });
    container.appendChild(card);
  }

  // Toggle all button
  document.getElementById('sb-toggle-all').addEventListener('click', () => {
    const cards = container.querySelectorAll('.sb-cat-card');
    const allChecked = [...cards].every(c => c.querySelector('input').checked);
    cards.forEach(c => {
      c.querySelector('input').checked = !allChecked;
      c.classList.toggle('active', !allChecked);
    });
    updateSbToggleAllBtn();
  });

  function updateSbToggleAllBtn() {
    const cards = container.querySelectorAll('.sb-cat-card');
    const allChecked = [...cards].every(c => c.querySelector('input').checked);
    document.getElementById('sb-toggle-all').textContent = allChecked ? 'Deselect All' : 'Select All';
  }
}

function initBitrateMode() {
  const tabs = document.querySelectorAll('.bitrate-mode-tab');
  const panels = {
    auto: document.getElementById('bitrate-panel-auto'),
    'per-resolution': document.getElementById('bitrate-panel-per-resolution'),
    custom: document.getElementById('bitrate-panel-custom'),
  };

  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      Object.values(panels).forEach(p => { if (p) p.style.display = 'none'; });
      const target = panels[tab.dataset.mode];
      if (target) target.style.display = '';
    });
  });
}

function getBitrateSettings() {
  const activeTab = document.querySelector('.bitrate-mode-tab.active');
  const mode = activeTab?.dataset.mode || 'auto';

  if (mode === 'per-resolution') {
    return {
      mode: 'per-resolution',
      per_resolution: {
        2160: parseInt(document.getElementById('br-2160')?.value) || 45,
        1440: parseInt(document.getElementById('br-1440')?.value) || 30,
        1080: parseInt(document.getElementById('br-1080')?.value) || 15,
        720: parseInt(document.getElementById('br-720')?.value) || 10,
        480: parseInt(document.getElementById('br-480')?.value) || 5,
      },
    };
  } else if (mode === 'custom') {
    return {
      mode: 'custom',
      custom_bitrate: parseInt(document.getElementById('br-custom')?.value) || 15,
    };
  }
  return { mode: 'auto' };
}

function applyBitrateSettings(encoding) {
  if (!encoding) return;

  const mode = encoding.bitrate_mode || 'auto';

  // Activate the correct tab
  document.querySelectorAll('.bitrate-mode-tab').forEach(tab => {
    tab.classList.toggle('active', tab.dataset.mode === mode);
  });

  // Show the correct panel
  ['auto', 'per-resolution', 'custom'].forEach(m => {
    const panel = document.getElementById(`bitrate-panel-${m}`);
    if (panel) panel.style.display = (m === mode) ? '' : 'none';
  });

  // Set per-resolution values
  if (encoding.per_resolution) {
    for (const [h, v] of Object.entries(encoding.per_resolution)) {
      const input = document.getElementById(`br-${h}`);
      if (input) input.value = v;
    }
  }

  // Set custom bitrate value
  if (encoding.custom_bitrate) {
    const input = document.getElementById('br-custom');
    if (input) input.value = encoding.custom_bitrate;
  }
}

async function loadSettings() {
  try {
    const result = await invoke('load_settings');
    appConfig = result.config || {};
    appSettings = result.settings || {};
    applySettings();
  } catch {
    // Settings not available yet — use defaults
    appConfig = { output_dir: '' };
    appSettings = {};
  }
}

function applySettings() {
  // Output dir
  if (appConfig.output_dir) {
    document.getElementById('output-dir-display').textContent = appConfig.output_dir;
  }

  // Cookies
  if (appSettings.cookies?.enabled) {
    document.getElementById('settings-cookies-enabled').checked = true;
  }

  // SponsorBlock
  if (appSettings.sponsorblock?.enabled !== undefined) {
    document.getElementById('toggle-sponsorblock').checked = appSettings.sponsorblock.enabled;
    document.getElementById('settings-sb-enabled').checked = appSettings.sponsorblock.enabled;
  }

  // Bitrate mode
  applyBitrateSettings(appSettings.encoding);
}

async function testCookies() {
  const browser = document.getElementById('settings-cookies-browser').value;
  const profile = document.getElementById('settings-cookies-profile').value;
  const resultEl = document.getElementById('cookie-test-result');

  if (!browser) {
    resultEl.textContent = 'Select a browser first';
    resultEl.style.color = '';
    return;
  }

  resultEl.textContent = 'Testing cookies...';
  resultEl.style.color = '';

  try {
    const result = await invoke('test_cookies', { browser, profile: profile || '' });
    if (result.success) {
      resultEl.innerHTML = '<span style="color:var(--green);font-weight:600">Cookies are working!</span>';
    } else {
      resultEl.innerHTML = `<span style="color:var(--red);font-weight:600">Test failed</span> &mdash; ${escapeHtml(result.message || 'Could not extract cookies')}`;
    }
  } catch (e) {
    resultEl.innerHTML = `<span style="color:var(--red);font-weight:600">Error</span> &mdash; ${escapeHtml(String(e))}`;
  }
}

let detectedBrowsers = [];

async function detectBrowsers() {
  const btn = document.getElementById('btn-refresh-browsers');
  btn.disabled = true;
  btn.textContent = 'Scanning...';

  try {
    const result = await invoke('detect_browsers');
    detectedBrowsers = result.browsers || [];
    const select = document.getElementById('settings-cookies-browser');
    const current = select.value;
    select.innerHTML = '<option value="">Select browser...</option>';

    const browserLabels = { chrome: 'Google Chrome', firefox: 'Mozilla Firefox', edge: 'Microsoft Edge', safari: 'Safari' };
    for (const b of detectedBrowsers) {
      const opt = document.createElement('option');
      opt.value = b.browser;
      opt.textContent = browserLabels[b.browser] || b.browser;
      select.appendChild(opt);
    }
    if (current) select.value = current;
    populateProfiles();
  } catch (e) {
    addLog('debug', `Browser detection failed: ${e}`);
  }

  btn.disabled = false;
  btn.textContent = 'Refresh';
}

function populateProfiles() {
  const browser = document.getElementById('settings-cookies-browser').value;
  const select = document.getElementById('settings-cookies-profile');
  select.innerHTML = '<option value="">Select profile...</option>';

  const entry = detectedBrowsers.find(b => b.browser === browser);
  if (!entry) return;

  for (const p of (entry.profiles || [])) {
    const opt = document.createElement('option');
    opt.value = p.name;
    const label = p.is_default ? `${p.name} (Personal)` : p.name;
    opt.textContent = label;
    select.appendChild(opt);
  }
}

function checkProfileWarning() {
  const profile = document.getElementById('settings-cookies-profile').value.toLowerCase();
  const warning = document.getElementById('cookie-profile-warning');
  const isDefault = profile.includes('default') || profile.includes('personal') || profile === '';
  warning.style.display = (profile && isDefault) ? '' : 'none';
}

// ============ Burner Account Guide ============
function initBurnerGuide() {
  const modal = document.getElementById('burner-guide-modal');
  const tabs = document.querySelectorAll('.burner-tab');
  const panels = { chrome: 'btab-chrome', firefox: 'btab-firefox', safari: 'btab-safari' };

  // Open guide
  document.getElementById('btn-burner-guide').addEventListener('click', () => {
    modal.classList.add('visible');
  });

  // Close
  document.getElementById('burner-guide-close').addEventListener('click', () => {
    modal.classList.remove('visible');
  });

  // "I'm Done - Test My Cookies"
  document.getElementById('burner-guide-test').addEventListener('click', () => {
    modal.classList.remove('visible');
    switchPage('settings');
    testCookies();
  });

  // Overlay click to close
  modal.addEventListener('click', (e) => {
    if (e.target === modal) modal.classList.remove('visible');
  });

  // Browser tabs
  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      Object.values(panels).forEach(id => {
        document.getElementById(id).style.display = 'none';
      });
      document.getElementById(panels[tab.dataset.btab]).style.display = '';
    });
  });
}

let pendingUpdate = null;

async function checkYtdlpUpdate() {
  const statusEl = document.getElementById('update-status');
  statusEl.textContent = 'Checking...';

  try {
    const result = await invoke('check_ytdlp_update');

    if (result.update_available) {
      statusEl.textContent = `Update available: ${result.stable_version}`;
      statusEl.style.color = 'var(--orange)';

      // Update version pill
      const pill = document.getElementById('version-pill');
      pill.classList.add('update-available');

      // Show update popup
      pendingUpdate = result;
      document.getElementById('update-current-ver').textContent = `Current: ${result.current_version || '?'}`;
      document.getElementById('update-new-ver').textContent = `New: ${result.stable_version}`;
      document.getElementById('update-modal').classList.add('visible');
    } else {
      statusEl.textContent = `Up to date: ${result.current_version || 'unknown'}`;
      statusEl.style.color = 'var(--green)';
    }

    document.getElementById('ytdlp-version').textContent = `yt-dlp ${result.current_version || '?'}`;
  } catch (e) {
    statusEl.textContent = `Error: ${e}`;
    statusEl.style.color = 'var(--red)';
  }
}

function initUpdateModal() {
  const modal = document.getElementById('update-modal');

  document.getElementById('update-btn-dismiss').addEventListener('click', () => {
    modal.classList.remove('visible');
  });

  modal.addEventListener('click', (e) => {
    if (e.target === modal) modal.classList.remove('visible');
  });

  document.getElementById('update-btn-install').addEventListener('click', async () => {
    if (!pendingUpdate) return;

    const btn = document.getElementById('update-btn-install');
    btn.disabled = true;
    btn.innerHTML = `
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spin"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/></svg>
      Installing...
    `;

    try {
      await invoke('install_ytdlp_update', {
        version: pendingUpdate.stable_version,
        nightly: false,
      });

      btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg> Updated!`;
      btn.style.background = 'var(--green)';

      // Update status in settings
      const statusEl = document.getElementById('update-status');
      statusEl.textContent = `Up to date: ${pendingUpdate.stable_version}`;
      statusEl.style.color = 'var(--green)';
      document.getElementById('ytdlp-version').textContent = `yt-dlp ${pendingUpdate.stable_version}`;
      document.getElementById('version-pill')?.classList.remove('update-available');

      addLog('info', `yt-dlp updated to ${pendingUpdate.stable_version}`);

      setTimeout(() => modal.classList.remove('visible'), 1500);
    } catch (e) {
      btn.disabled = false;
      btn.innerHTML = `Update Failed — Retry`;
      btn.style.background = '';
      addLog('error', `yt-dlp update failed: ${e}`);
    }
  });
}

// ============ Chapter Modal ============
function initChapterModal() {
  const modal = document.getElementById('chapter-modal');

  document.getElementById('chapters-link').addEventListener('click', () => {
    const info = getVideoInfo();
    if (!info?.chapters?.length) return;
    renderChapterList(info.chapters);
    modal.classList.add('visible');
  });

  document.getElementById('chapters-cancel').addEventListener('click', () => {
    modal.classList.remove('visible');
  });

  document.getElementById('chapters-select-all').addEventListener('click', () => {
    modal.querySelectorAll('input[type=checkbox]').forEach(cb => cb.checked = true);
  });

  document.getElementById('chapters-select-none').addEventListener('click', () => {
    modal.querySelectorAll('input[type=checkbox]').forEach(cb => cb.checked = false);
  });

  document.getElementById('chapters-download').addEventListener('click', () => {
    // Collect selected chapters
    const selected = [];
    modal.querySelectorAll('.chapter-item').forEach(item => {
      const cb = item.querySelector('input[type=checkbox]');
      if (cb?.checked) {
        selected.push({
          title: item.dataset.title,
          start_time: parseFloat(item.dataset.start),
          end_time: parseFloat(item.dataset.end),
        });
      }
    });

    if (selected.length === 0) return;

    modal.classList.remove('visible');
    startChapterDownload(selected);
  });

  modal.addEventListener('click', (e) => {
    if (e.target === modal) modal.classList.remove('visible');
  });
}

function renderChapterList(chapters) {
  const list = document.getElementById('chapter-list');
  list.innerHTML = '';

  for (let i = 0; i < chapters.length; i++) {
    const ch = chapters[i];
    const item = document.createElement('div');
    item.className = 'chapter-item';
    item.dataset.title = ch.title;
    item.dataset.start = ch.start_time;
    item.dataset.end = ch.end_time;

    item.innerHTML = `
      <input type="checkbox" checked>
      <label>${i + 1}. ${escapeHtml(ch.title)}</label>
      <span class="chapter-time">${ch.duration_str || ''}</span>
    `;
    list.appendChild(item);
  }
}

// ============ Utilities ============
function escapeHtml(str) {
  if (!str) return '';
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function formatDate(dateStr) {
  if (!dateStr) return '';
  try {
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  } catch {
    return '';
  }
}

// ============ Start ============
document.addEventListener('DOMContentLoaded', init);
