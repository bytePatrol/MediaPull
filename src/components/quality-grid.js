/**
 * Quality card selection and rendering logic.
 */

let selectedQuality = null;
let onQualityChange = null;

const QUALITY_ORDER = [2160, 1440, 1080, 720, 480];

const QUALITY_LABELS = {
  2160: '4K',
  1440: '1440p',
  1080: '1080p',
  720: '720p',
  480: '480p',
};

export function initQualityGrid(onChange) {
  onQualityChange = onChange;
}

export function renderQualityGrid(formats) {
  const grid = document.getElementById('quality-grid');
  grid.innerHTML = '';

  // Playlist mode: show all standard presets without format-specific data
  if (!formats) {
    const defaultHeight = 1080;
    selectedQuality = defaultHeight;

    for (const h of QUALITY_ORDER) {
      const card = document.createElement('div');
      card.className = 'q-card';
      card.dataset.quality = h;

      if (h === defaultHeight) card.classList.add('selected');

      const qRes = document.createElement('div');
      qRes.className = 'q-res';
      qRes.textContent = QUALITY_LABELS[h] || `${h}p`;
      card.appendChild(qRes);

      card.addEventListener('click', () => selectQuality(h));
      grid.appendChild(card);
    }

    // Audio Only card
    const audioCard = document.createElement('div');
    audioCard.className = 'q-card audio-card';
    audioCard.dataset.quality = 'audio';
    audioCard.innerHTML = `
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
        <path d="M9 18V5l12-2v13"/>
        <circle cx="6" cy="18" r="3"/>
        <circle cx="18" cy="16" r="3"/>
      </svg>
      <span class="q-audio-label">Audio Only</span>
      <span class="q-audio-sub">M4A</span>
    `;
    audioCard.addEventListener('click', () => selectQuality('audio'));
    grid.appendChild(audioCard);

    if (onQualityChange) onQualityChange(selectedQuality);
    return;
  }

  // Group formats by height and pick best per resolution
  const byHeight = {};
  for (const fmt of formats) {
    if (!fmt.height || fmt.height < 360) continue;
    if (fmt.format_note === 'audio only') continue;

    // Snap to nearest standard resolution
    const snapHeight = snapToResolution(fmt.height);
    if (!byHeight[snapHeight] || fmt.tbr > (byHeight[snapHeight].tbr || 0)) {
      byHeight[snapHeight] = fmt;
    }
  }

  // Find the "best" recommendation (highest H.264 or highest available)
  let bestHeight = 0;
  for (const h of QUALITY_ORDER) {
    if (byHeight[h]) {
      const fmt = byHeight[h];
      if (h <= 1080 && (fmt.vcodec || '').startsWith('avc1')) {
        bestHeight = h;
        break;
      }
      if (!bestHeight) bestHeight = h;
    }
  }

  // Determine default selection (highest available)
  let defaultHeight = 0;
  for (const h of QUALITY_ORDER) {
    if (byHeight[h]) {
      defaultHeight = h;
      break;
    }
  }

  // Render cards
  for (const h of QUALITY_ORDER) {
    const fmt = byHeight[h];
    if (!fmt) continue;

    const card = document.createElement('div');
    card.className = 'q-card';
    card.dataset.quality = h;

    if (h === defaultHeight) {
      card.classList.add('selected');
      selectedQuality = h;
    }

    // Best badge
    if (h === bestHeight) {
      const badge = document.createElement('span');
      badge.className = 'best-badge';
      badge.textContent = 'Best';
      card.appendChild(badge);
    }

    // Codec badge
    const qBadge = document.createElement('span');
    qBadge.className = 'q-badge';
    qBadge.textContent = getCodecLabel(fmt);
    card.appendChild(qBadge);

    // Resolution
    const qRes = document.createElement('div');
    qRes.className = 'q-res';
    qRes.textContent = QUALITY_LABELS[h] || `${h}p`;
    card.appendChild(qRes);

    // Codec detail
    const qCodec = document.createElement('div');
    qCodec.className = 'q-codec';
    qCodec.textContent = getCodecDetail(fmt);
    card.appendChild(qCodec);

    // Size estimate
    const qSize = document.createElement('div');
    qSize.className = 'q-size';
    qSize.textContent = formatSize(fmt.filesize || fmt.filesize_approx);
    card.appendChild(qSize);

    card.addEventListener('click', () => selectQuality(h));
    grid.appendChild(card);
  }

  // Audio Only card
  const audioCard = document.createElement('div');
  audioCard.className = 'q-card audio-card';
  audioCard.dataset.quality = 'audio';
  audioCard.innerHTML = `
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <path d="M9 18V5l12-2v13"/>
      <circle cx="6" cy="18" r="3"/>
      <circle cx="18" cy="16" r="3"/>
    </svg>
    <span class="q-audio-label">Audio Only</span>
    <span class="q-audio-sub">M4A</span>
  `;
  audioCard.addEventListener('click', () => selectQuality('audio'));
  grid.appendChild(audioCard);

  // Trigger initial callback
  if (onQualityChange && selectedQuality) {
    onQualityChange(selectedQuality);
  }
}

function selectQuality(quality) {
  selectedQuality = quality;
  document.querySelectorAll('.q-card').forEach(c => {
    c.classList.toggle('selected', c.dataset.quality == quality);
  });
  if (onQualityChange) onQualityChange(quality);
}

export function getSelectedQuality() {
  return selectedQuality;
}

function snapToResolution(height) {
  if (height >= 2000) return 2160;
  if (height >= 1300) return 1440;
  if (height >= 900) return 1080;
  if (height >= 600) return 720;
  return 480;
}

function getCodecLabel(fmt) {
  const codec = (fmt.vcodec || '').toLowerCase();
  if (codec.startsWith('avc1') || codec.startsWith('h264')) return 'H.264';
  if (codec.startsWith('vp9') || codec.startsWith('vp09')) return 'VP9';
  if (codec.startsWith('av01')) return 'AV1';
  if (fmt.height >= 2160) return '4K';
  return `${fmt.height}`;
}

function getCodecDetail(fmt) {
  const codec = (fmt.vcodec || '').toLowerCase();
  if (codec.startsWith('avc1') || codec.startsWith('h264')) return 'H.264';
  if (codec.startsWith('vp9') || codec.startsWith('vp09')) return 'VP9';
  if (codec.startsWith('av01')) return 'AV1';
  return fmt.ext || 'MP4';
}

function formatSize(bytes) {
  if (!bytes) return '';
  if (bytes >= 1024 * 1024 * 1024) return `~${(bytes / (1024**3)).toFixed(1)} GB`;
  if (bytes >= 1024 * 1024) return `~${(bytes / (1024**2)).toFixed(0)} MB`;
  return `~${(bytes / 1024).toFixed(0)} KB`;
}
