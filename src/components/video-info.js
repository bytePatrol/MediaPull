/**
 * Video info panel rendering.
 */

let currentVideoInfo = null;

export function showVideoInfo(info) {
  currentVideoInfo = info;

  const panel = document.getElementById('video-info');
  panel.classList.add('visible');

  // Thumbnail
  const img = document.getElementById('thumb-img');
  if (info.thumbnail_url) {
    img.src = info.thumbnail_url;
    img.style.display = 'block';
  } else {
    img.style.display = 'none';
  }

  // Duration
  document.getElementById('thumb-duration').textContent = info.duration_str || '';

  // Title
  document.getElementById('meta-title').textContent = info.title || 'Unknown';

  // Subtitle line
  const parts = [];
  if (info.channel) parts.push(`<strong>${escapeHtml(info.channel)}</strong>`);
  if (info.duration_str) parts.push(info.duration_str);
  if (info.views_str) parts.push(info.views_str);
  if (info.upload_date) {
    const formatted = formatDate(info.upload_date);
    if (formatted) parts.push(formatted);
  }
  document.getElementById('meta-sub').innerHTML = parts.join(' &middot; ');

  // Chapters link
  const chaptersLink = document.getElementById('chapters-link');
  const chaptersCount = document.getElementById('chapters-count');
  if (info.chapters && info.chapters.length > 0) {
    chaptersLink.style.display = 'inline-flex';
    chaptersCount.textContent = `${info.chapters.length} chapters available`;
  } else {
    chaptersLink.style.display = 'none';
  }
}

export function hideVideoInfo() {
  document.getElementById('video-info').classList.remove('visible');
  currentVideoInfo = null;
}

export function getVideoInfo() {
  return currentVideoInfo;
}

function formatDate(dateStr) {
  if (!dateStr || dateStr.length !== 8) return '';
  try {
    const y = dateStr.slice(0, 4);
    const m = parseInt(dateStr.slice(4, 6)) - 1;
    const d = dateStr.slice(6, 8);
    const date = new Date(y, m, d);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  } catch {
    return '';
  }
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}
