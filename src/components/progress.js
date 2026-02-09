/**
 * Progress bar and stats updates.
 */

const STAGE_LABELS = {
  download_video: 'Downloading video...',
  download_audio: 'Downloading audio...',
  convert: 'Encoding...',
  sponsorblock: 'Removing sponsors...',
  split_chapters: 'Splitting chapters...',
  complete: 'Complete!',
  download_video_retry: 'Retrying video download...',
  download_audio_retry: 'Retrying audio download...',
  analyze: 'Analyzing...',
  update: 'Updating yt-dlp...',
};

export function showProgress() {
  document.getElementById('progress-section').classList.add('visible');
}

export function hideProgress() {
  document.getElementById('progress-section').classList.remove('visible');
}

export function updateProgress(stage, percent, speedMbps, etaSeconds, fps) {
  const bar = document.getElementById('progress-bar');
  const label = document.getElementById('progress-label');

  bar.style.width = `${Math.min(percent, 100)}%`;
  label.textContent = STAGE_LABELS[stage] || stage;

  // Update stats
  if (speedMbps > 0) {
    document.getElementById('stat-speed').textContent = `${speedMbps.toFixed(1)} MB/s`;
  }
  if (etaSeconds > 0) {
    document.getElementById('stat-eta').textContent = formatEta(etaSeconds);
  }
  if (fps > 0) {
    document.getElementById('stat-fps').textContent = `${fps.toFixed(0)}`;
  }
}

export function resetProgress() {
  document.getElementById('progress-bar').style.width = '0%';
  document.getElementById('progress-label').textContent = 'Preparing...';
  document.getElementById('stat-speed').innerHTML = '&mdash;';
  document.getElementById('stat-eta').innerHTML = '&mdash;';
  document.getElementById('stat-size').innerHTML = '&mdash;';
  document.getElementById('stat-fps').innerHTML = '&mdash;';
}

function formatEta(seconds) {
  if (seconds <= 0) return '--:--';
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  if (m >= 60) {
    const h = Math.floor(m / 60);
    const rm = m % 60;
    return `${h}:${String(rm).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  }
  return `${m}:${String(s).padStart(2, '0')}`;
}
