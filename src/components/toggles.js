/**
 * Toggle/option state management.
 */

const state = {
  sponsorblock: true,
  subtitles: false,
  trimStart: '',
  trimEnd: '',
};

export function initToggles() {
  // SponsorBlock toggle
  const sbToggle = document.getElementById('toggle-sponsorblock');
  sbToggle.addEventListener('change', () => {
    state.sponsorblock = sbToggle.checked;
  });

  // Subtitles toggle
  const subToggle = document.getElementById('toggle-subtitles');
  subToggle.addEventListener('change', () => {
    state.subtitles = subToggle.checked;
  });

  // Trim modal
  const btnTrim = document.getElementById('btn-trim');
  const trimModal = document.getElementById('trim-modal');
  const trimCancel = document.getElementById('trim-cancel');
  const trimApply = document.getElementById('trim-apply');

  btnTrim.addEventListener('click', () => {
    document.getElementById('trim-start').value = state.trimStart;
    document.getElementById('trim-end').value = state.trimEnd;
    trimModal.classList.add('visible');
  });

  trimCancel.addEventListener('click', () => {
    trimModal.classList.remove('visible');
  });

  trimApply.addEventListener('click', () => {
    state.trimStart = document.getElementById('trim-start').value.trim();
    state.trimEnd = document.getElementById('trim-end').value.trim();
    trimModal.classList.remove('visible');

    // Update trim button appearance
    if (state.trimStart || state.trimEnd) {
      btnTrim.style.borderColor = 'var(--accent)';
      btnTrim.style.color = 'var(--accent)';
    } else {
      btnTrim.style.borderColor = '';
      btnTrim.style.color = '';
    }
  });

  // Close modal on overlay click
  trimModal.addEventListener('click', (e) => {
    if (e.target === trimModal) trimModal.classList.remove('visible');
  });
}

export function getOptions() {
  return { ...state };
}

export function resetTrim() {
  state.trimStart = '';
  state.trimEnd = '';
  const btnTrim = document.getElementById('btn-trim');
  btnTrim.style.borderColor = '';
  btnTrim.style.color = '';
}
