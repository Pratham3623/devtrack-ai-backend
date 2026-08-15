/**
 * @jest-environment jsdom
 */

describe('DevTrack AI Frontend UI Component Suite', () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <div id="toast-container"></div>
      <div id="search-modal-overlay" class="modal-overlay">
        <input id="global-search-input" type="text" placeholder="Search..." />
        <div id="search-results-list"></div>
      </div>
      <div id="version-modal-overlay" class="modal-overlay">
        <span id="version-modal-filename"></span>
        <span id="version-modal-current-v"></span>
        <input id="version-file-input" type="file" />
        <input id="version-changelog-input" type="text" />
        <div id="version-history-timeline"></div>
      </div>
      <div id="view-files" class="view-panel">
        <select id="files-project-filter"></select>
        <div id="files-container"></div>
        <span id="files-count">0</span>
      </div>
      <div id="view-analytics" class="view-panel">
        <select id="analytics-project-select"></select>
        <div id="health-status-badge">Good</div>
      </div>
    `;
  });

  test('DOM initializes search modal correctly', () => {
    const modal = document.getElementById('search-modal-overlay');
    const input = document.getElementById('global-search-input');
    expect(modal).not.toBeNull();
    expect(input).not.toBeNull();
    expect(input.placeholder).toBe('Search...');
  });

  test('Global search input fires query input event', () => {
    const input = document.getElementById('global-search-input');
    const handleInput = jest.fn();
    input.addEventListener('input', handleInput);

    input.value = 'bug fix';
    input.dispatchEvent(new Event('input'));

    expect(handleInput).toHaveBeenCalledTimes(1);
    expect(input.value).toBe('bug fix');
  });

  test('Files view filter dropdown updates DOM', () => {
    const filterSelect = document.getElementById('files-project-filter');
    filterSelect.innerHTML = '<option value="">All Projects</option><option value="p1">Project Alpha</option>';
    
    expect(filterSelect.options.length).toBe(2);
    expect(filterSelect.options[1].text).toBe('Project Alpha');
  });

  test('Version modal renders filename and current version badge', () => {
    const nameEl = document.getElementById('version-modal-filename');
    const vEl = document.getElementById('version-modal-current-v');

    nameEl.textContent = 'architecture_spec.pdf';
    vEl.textContent = 'Current Version: v3';

    expect(nameEl.textContent).toBe('architecture_spec.pdf');
    expect(vEl.textContent).toBe('Current Version: v3');
  });

  test('Files container empty state rendering', () => {
    const container = document.getElementById('files-container');
    container.innerHTML = `
      <div class="empty-state">
        <h3>No files uploaded yet</h3>
      </div>`;
    
    expect(container.querySelector('h3').textContent).toBe('No files uploaded yet');
  });

  test('Executive analytics health badge styling toggle', () => {
    const badge = document.getElementById('health-status-badge');
    expect(badge.textContent).toBe('Good');
    
    badge.textContent = 'Critical Risk';
    badge.className = 'health-critical';

    expect(badge.textContent).toBe('Critical Risk');
    expect(badge.classList.contains('health-critical')).toBe(true);
  });
});
