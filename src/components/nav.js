/**
 * Sidebar navigation and view switching.
 */

const pages = ['downloader', 'library', 'settings', 'logs', 'help'];

export function initNav() {
  const nav = document.getElementById('nav');
  const navItems = nav.querySelectorAll('.nav-item');

  navItems.forEach(item => {
    item.addEventListener('click', () => {
      const page = item.dataset.page;
      switchPage(page);
    });
  });

  // Log link in status bar switches to logs page
  document.getElementById('log-link')?.addEventListener('click', () => {
    switchPage('logs');
  });
}

export function switchPage(pageName) {
  // Update nav
  document.querySelectorAll('.nav-item').forEach(item => {
    item.classList.toggle('active', item.dataset.page === pageName);
  });

  // Update pages
  pages.forEach(name => {
    const el = document.getElementById(`page-${name}`);
    if (el) {
      el.classList.toggle('active', name === pageName);
    }
  });
}
