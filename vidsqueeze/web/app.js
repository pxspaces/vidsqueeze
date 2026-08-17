/* VidSqueeze interface.
   Sources on the left, workspace in the middle, results on the right. The
   settings form is the single source of truth: presets fill it in, and whatever
   it holds when Squeeze is pressed is what runs. */

const TOKEN = document.documentElement.dataset.token;
const $ = (id) => document.getElementById(id);

const state = {
  paths: [],        // what the user picked, folders included
  files: [],        // details of the media files those expand to
  results: {},      // source path -> queue item
  selectedSource: null,
  selectedResult: null,
  presets: [],
  settings: {},
  imageFormats: {},
  kinds: [],
  browserPath: null,
  browserMode: 'files',   // files | folder | watch
  polling: null,
  samplePolling: null,
  watchPolling: null,
  watchFolder: '',
  duration: 0,
  compareMode: 'frames',
  lastChecked: -1,
  activePreset: '',
  mode: 'any',
  rawSupport: null,
  appVersion: '',
};

/* ---------- server ---------- */

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      'X-VidSqueeze-Token': TOKEN,
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
    },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
  return data;
}
const post = (path, body) => api(path, { method: 'POST', body: JSON.stringify(body || {}) });
const show = (id, visible) => { const el = $(id); if (el) el.hidden = !visible; };
const setText = (el, value) => { if (el) el.textContent = value == null ? '' : String(value); };
const mediaUrl = (p) => `/api/media?token=${encodeURIComponent(TOKEN)}&path=${encodeURIComponent(p)}`;
const frameUrl = (p, t, w) =>
  `/api/frame?token=${encodeURIComponent(TOKEN)}&path=${encodeURIComponent(p)}&t=${Number(t).toFixed(2)}&w=${w}`;

function formatTime(seconds) {
  seconds = Math.max(0, Math.round(seconds));
  const m = Math.floor(seconds / 60);
  if (m >= 60) return `${Math.floor(m / 60)}h ${m % 60}m`;
  if (m) return `${m}m ${seconds % 60}s`;
  return `${seconds}s`;
}
function clockTime(seconds) {
  const s = Math.max(0, Math.round(seconds || 0));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}
function humanTotal(bytes) {
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let size = bytes || 0, i = 0;
  while (size >= 1024 && i < units.length - 1) { size /= 1024; i += 1; }
  return `${i === 0 ? Math.round(size) : size.toFixed(1)} ${units[i]}`;
}

/* ---------- startup ---------- */

async function boot() {
  let info;
  try {
    info = await api('/api/state');
  } catch (error) {
    document.body.innerHTML =
      `<div class="centre-screen"><div class="panel"><h1 class="display">VidSqueeze could not start</h1><p class="muted">${error.message}</p></div></div>`;
    return;
  }

  state.presets = info.presets;
  state.settings = info.settings || {};
  state.imageFormats = info.image_formats || {};
  state.rawSupport = info.raw || null;
  state.appVersion = info.app_version || '';
  state.mode = state.settings.media_mode || 'any';

  setText($('outputPath'), state.settings.output_dir || info.output_dir);
  setText($('freeSpace'), info.free_space);
  setText($('setupSize'), info.download_size);
  setText($('installHint'), info.install_hint);

  if (!info.ffmpeg) { show('setupScreen', true); return; }

  const badge = $('ffmpegBadge');
  setText(badge, `ffmpeg ${info.ffmpeg.version.split('-')[0]}`);
  badge.hidden = false;

  buildForm(info);
  buildImageForm();
  buildSpeedChoices(info);
  buildModeSelector();
  renderPresets();
  renderHistory(info.history);

  show('setupScreen', false);

  // Asked once, then never again unless they want to change it.
  if (!state.settings.asked_media_mode) {
    buildModeScreen();
    show('modeScreen', true);
    return;
  }
  enterWorkspace();
}

function enterWorkspace() {
  show('modeScreen', false);
  show('setupScreen', false);
  show('workspace', true);
  show('modeSelector', true);
  renderPresets();
  renderSources();
  renderResults();
}

/* ---------- what do you work with ---------- */

const MODES = [
  ['any', '\u2726', 'Anything', 'Video, audio and photos. Every setting available.'],
  ['video', '\u25B6', 'Video', 'Films and clips. Codecs, resolution, trimming.'],
  ['audio', '\u266A', 'Audio', 'Music and recordings, or pulling sound out of video.'],
  ['image', '\u25A3', 'Photos', 'Pictures and graphics, including camera RAW.'],
];

function buildModeScreen() {
  const host = $('modeChoices');
  host.innerHTML = '';
  for (const [value, glyph, name, description] of MODES) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'mode-choice';
    const icon = document.createElement('span');
    icon.className = 'glyph';
    icon.textContent = glyph;
    const text = document.createElement('span');
    const strong = document.createElement('strong');
    strong.textContent = name;
    const small = document.createElement('small');
    small.textContent = description;
    text.append(strong, small);
    button.append(icon, text);
    button.addEventListener('click', () => {
      setMode(value);
      post('/api/settings', { asked_media_mode: true }).catch(() => {});
      state.settings.asked_media_mode = true;
      enterWorkspace();
    });
    host.append(button);
  }
}

function buildModeSelector() {
  const host = $('modeSelector');
  host.innerHTML = '';
  for (const [value, , name] of MODES) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'seg';
    button.dataset.mode = value;
    button.textContent = name;
    button.setAttribute('aria-pressed', String(value === state.mode));
    button.addEventListener('click', () => setMode(value));
    host.append(button);
  }
}

/* The mode narrows what is listed and what a folder brings in. "Anything"
   applies no filter at all. */
function modeKinds() {
  return state.mode === 'any' ? null : [state.mode];
}
function kindsParam() {
  const kinds = modeKinds();
  return kinds ? `&kinds=${encodeURIComponent(kinds.join(','))}` : '';
}

function setMode(value) {
  state.mode = value;
  for (const button of $('modeSelector').querySelectorAll('.seg')) {
    button.setAttribute('aria-pressed', String(button.dataset.mode === value));
  }
  post('/api/settings', { media_mode: value }).catch(() => {});
  state.settings.media_mode = value;
  renderPresets();
  // A different mode means a different set of files is relevant, so anything
  // already chosen is re-read through the new filter.
  if (state.paths.length) refreshSelection();
  if (!$('browser').hidden && state.browserPath) loadFolder(state.browserPath);
}

/* ---------- setup and upgrade ---------- */

function watchSetup(onDone) {
  const timer = setInterval(async () => {
    const status = await api('/api/setup').catch(() => null);
    if (!status) return;
    setText($('setupMessage'), status.message || '');
    const bar = $('setupBar');
    if (bar) bar.style.width = status.fraction >= 0 ? `${status.fraction * 100}%` : '100%';
    if (status.error) {
      clearInterval(timer);
      setText($('setupError'), status.error);
      show('setupError', true);
      $('setupBtn').disabled = false;
      $('upgradeBtn').disabled = false;
    } else if (!status.running && (status.done || status.installed)) {
      clearInterval(timer);
      onDone();
    }
  }, 600);
}

$('setupBtn').addEventListener('click', async () => {
  $('setupBtn').disabled = true;
  show('setupProgress', true);
  show('setupError', false);
  await post('/api/setup/start');
  watchSetup(boot);
});

$('upgradeBtn').addEventListener('click', async () => {
  const button = $('upgradeBtn');
  button.disabled = true;
  setText($('upgradeText'), 'Downloading a newer ffmpeg. This takes a moment.');
  try {
    await post('/api/upgrade');
  } catch (error) {
    setText($('upgradeText'), error.message);
    button.disabled = false;
    return;
  }
  watchSetup(async () => {
    show('upgradeOffer', false);
    button.disabled = false;
    await boot();
    refreshSelection();
  });
});

/* ---------- settings form ---------- */

function fillSelect(select, entries, selected) {
  select.innerHTML = '';
  for (const [value, label] of entries) {
    const option = document.createElement('option');
    option.value = value;
    option.textContent = label;
    if (String(value) === String(selected)) option.selected = true;
    select.append(option);
  }
}

function buildForm(info) {
  const { codecs, qualities, speeds } = info.options;
  fillSelect($('videoCodec'), Object.entries(codecs), info.defaults.video_codec);
  fillSelect($('container'), Object.keys(info.options.containers).map((c) => [c, `.${c}`]), info.defaults.container);
  fillSelect($('quality'), Object.entries(qualities), info.defaults.quality);
  fillSelect($('speed'), speeds.map((s) => [s, s]), info.defaults.speed);
  fillSelect($('audioCodec'), [
    ['opus', 'Opus (smallest)'], ['aac', 'AAC (most compatible)'], ['mp3', 'MP3'],
    ['flac', 'FLAC (lossless)'], ['copy', 'Keep as-is'], ['none', 'Remove audio'],
  ], info.defaults.audio_codec);

  $('qualityMode').addEventListener('change', syncQualityMode);
  syncQualityMode();

  if (info.max_concurrency > 1) {
    show('concurrencyRow', true);
    $('concurrency').checked = Number(state.settings.concurrency || 1) > 1;
  }
  if (state.settings.replace_originals) $('replaceOriginals').checked = true;
  if (state.settings.recursive === false) $('recursive').checked = false;
}

function buildImageForm() {
  const entries = Object.entries(state.imageFormats)
    .filter(([, spec]) => spec.available)
    .map(([key, spec]) => [key, spec.label]);
  fillSelect($('imageFormat'), entries, 'jpeg');
  $('imageFormat').addEventListener('change', syncImageForm);
  $('imageQuality').addEventListener('input', () => {
    setText($('imageQualityValue'), $('imageQuality').value);
  });
  $('imageLossless').addEventListener('change', syncImageForm);
  syncImageForm();
}

function syncImageForm() {
  const key = $('imageFormat').value;
  const spec = state.imageFormats[key] || {};
  setText($('imageFormatNote'), spec.note || '');
  const losslessCapable = key === 'webp' || key === 'jxl';
  show('imageLosslessRow', losslessCapable);
  if (!losslessCapable) $('imageLossless').checked = false;
  // Formats with no quality dial at all.
  const hasQuality = !['png', 'tiff', 'bmp'].includes(key) && !$('imageLossless').checked;
  show('imageQualityField', hasQuality);
  show('imageBackgroundField', !spec.alpha);
}

function syncQualityMode() {
  const mode = $('qualityMode').value;
  show('qualityField', mode === 'quality');
  show('sizeField', mode === 'size');
  show('bitrateField', mode === 'bitrate');
}

function buildSpeedChoices(info) {
  const hardware = info.hardware || [];
  const container = $('speedChoices');
  container.innerHTML = '';
  const choices = [['off', 'Best quality', 'Uses the processor. Smallest files for a given quality.']];
  if (hardware.length) {
    const vendors = [...new Set(hardware.map((h) => h.vendor))].join(', ');
    const codecList = hardware.map((h) => h.codec.toUpperCase()).join(' and ');
    choices.push(['auto', 'Much faster',
      `Uses your ${vendors} hardware for ${codecList}. Roughly twice as fast, but files come out noticeably larger at the same setting.`]);
  }
  for (const [value, label] of choices) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'seg';
    button.dataset.value = value;
    button.textContent = label;
    button.setAttribute('aria-pressed', String(value === (state.settings.hardware || 'off')));
    button.addEventListener('click', () => {
      for (const other of container.querySelectorAll('.seg')) {
        other.setAttribute('aria-pressed', String(other === button));
      }
      const found = choices.find((c) => c[0] === value);
      setText($('speedNote'), found ? found[2] : '');
      post('/api/settings', { hardware: value }).catch(() => {});
    });
    container.append(button);
  }
  const current = choices.find((c) => c[0] === (state.settings.hardware || 'off'));
  setText($('speedNote'), hardware.length
    ? (current ? current[2] : '')
    : 'No usable graphics card encoder was found on this computer, so encoding uses the processor.');
}

const currentHardware = () => {
  const active = $('speedChoices').querySelector('.seg[aria-pressed="true"]');
  return active ? active.dataset.value : 'off';
};

function applySpec(spec) {
  $('videoCodec').value = spec.video_codec;
  $('container').value = spec.container;
  $('audioCodec').value = spec.audio_codec;
  $('audioBitrate').value = String(spec.audio_bitrate);
  $('qualityMode').value = spec.quality_mode;
  $('quality').value = spec.quality;
  $('speed').value = spec.speed;
  $('scale').value = spec.scale ? String(spec.scale) : '';
  $('fpsMode').value = spec.fps_max ? String(spec.fps_max) : '';
  $('targetSize').value = spec.target_size_mb || 25;
  $('videoBitrate').value = spec.video_bitrate || 4000;
  $('trimStart').value = spec.trim_start ?? '';
  $('trimEnd').value = spec.trim_end ?? '';
  $('tenBit').checked = !!spec.ten_bit;
  $('tonemapHdr').checked = !!spec.tonemap_hdr;
  $('denoise').checked = !!spec.denoise;
  $('deinterlace').checked = !!spec.deinterlace;
  $('faststart').checked = !!spec.faststart;
  $('keepSubtitles').checked = !!spec.keep_subtitles;
  $('keepMetadata').checked = !!spec.keep_metadata;

  $('imageFormat').value = spec.image_format || 'jpeg';
  $('imageQuality').value = String(spec.image_quality ?? 82);
  setText($('imageQualityValue'), $('imageQuality').value);
  $('imageLossless').checked = !!spec.image_lossless;
  $('imageMaxDimension').value = spec.image_max_dimension ? String(spec.image_max_dimension) : '';
  $('imageBackground').value = spec.image_background || 'white';

  syncQualityMode();
  syncImageForm();
}

function readSpec() {
  const num = (id) => ($(id).value === '' ? null : Number($(id).value));
  return {
    video_codec: $('videoCodec').value,
    container: $('container').value,
    audio_codec: $('audioCodec').value,
    audio_bitrate: Number($('audioBitrate').value),
    quality_mode: $('qualityMode').value,
    quality: $('quality').value,
    speed: $('speed').value,
    scale: num('scale'),
    fps_max: num('fpsMode'),
    target_size_mb: num('targetSize'),
    video_bitrate: num('videoBitrate'),
    trim_start: num('trimStart'),
    trim_end: num('trimEnd'),
    ten_bit: $('tenBit').checked,
    tonemap_hdr: $('tonemapHdr').checked,
    denoise: $('denoise').checked,
    deinterlace: $('deinterlace').checked,
    faststart: $('faststart').checked,
    keep_subtitles: $('keepSubtitles').checked,
    keep_metadata: $('keepMetadata').checked,
    hardware: currentHardware(),
    image_format: $('imageFormat').value,
    image_quality: Number($('imageQuality').value),
    image_lossless: $('imageLossless').checked,
    image_max_dimension: num('imageMaxDimension'),
    image_background: $('imageBackground').value,
  };
}

/* ---------- presets, filtered by what is selected ---------- */

function renderPresets() {
  const host = $('presetGroups');
  host.innerHTML = '';

  // What is actually selected wins. With nothing selected, the chosen mode
  // decides, so the settings are never a wall of irrelevant options.
  const fromMode = state.mode === 'any' ? ['video', 'audio', 'image'] : [state.mode];
  const kinds = new Set(state.kinds.length ? state.kinds : fromMode);
  const relevant = state.presets.filter((p) => p.kinds.some((k) => kinds.has(k)));

  // Show only the settings that apply to what is actually selected.
  const onlyImages = kinds.size === 1 && kinds.has('image');
  show('advanced', !onlyImages);
  show('imageAdvanced', kinds.has('image'));
  show('speedBlock', !onlyImages);

  if (state.kinds.length > 1) {
    setText($('kindNotice'),
      `Your selection mixes ${state.kinds.join(' and ')}. Each file uses whichever settings apply to it.`);
    show('kindNotice', true);
  } else {
    show('kindNotice', false);
  }

  const groups = new Map();
  for (const preset of relevant) {
    if (!groups.has(preset.group)) groups.set(preset.group, []);
    groups.get(preset.group).push(preset);
  }
  for (const [name, items] of groups) {
    const section = document.createElement('div');
    section.className = 'preset-group';
    const heading = document.createElement('h4');
    heading.textContent = name;
    const grid = document.createElement('div');
    grid.className = 'preset-grid';
    for (const preset of items) {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'preset';
      button.dataset.key = preset.key;
      const strong = document.createElement('strong');
      strong.textContent = preset.name;
      const small = document.createElement('small');
      small.textContent = preset.description;
      button.append(strong, small);
      button.addEventListener('click', () => selectPreset(preset.key));
      grid.append(button);
    }
    section.append(heading, grid);
    host.append(section);
  }

  const stillValid = relevant.some((p) => p.key === state.activePreset);
  if (!stillValid && relevant.length) {
    const preferred = kinds.has('image') && !kinds.has('video') ? 'photo_web' : (state.settings.preset || 'balanced');
    selectPreset(relevant.some((p) => p.key === preferred) ? preferred : relevant[0].key);
  } else {
    markPreset(state.activePreset);
  }
}

function markPreset(key) {
  for (const button of document.querySelectorAll('.preset')) {
    button.setAttribute('aria-pressed', String(button.dataset.key === key));
  }
}

function selectPreset(key) {
  const preset = state.presets.find((p) => p.key === key);
  if (!preset) return;
  state.activePreset = key;
  markPreset(key);
  applySpec(preset.spec);
  post('/api/settings', { preset: key }).catch(() => {});
}

/* ---------- panes ---------- */

for (const button of document.querySelectorAll('.collapser')) {
  button.addEventListener('click', () => togglePane(button.dataset.collapse));
}
for (const pane of ['paneSources', 'paneResults']) {
  const rail = $(pane).querySelector('.rail');
  if (rail) rail.addEventListener('click', () => togglePane(pane));
}
function togglePane(id) {
  const pane = $(id);
  const shut = pane.classList.toggle('shut');
  $('workspace').classList.toggle(id === 'paneSources' ? 'left-shut' : 'right-shut', shut);
}

/* ---------- sources ---------- */

for (const id of ['addBtn', 'addBtnEmpty']) {
  $(id).addEventListener('click', () => openBrowser('files'));
}
$('clearBtn').addEventListener('click', () => {
  state.paths = []; state.files = []; state.results = {};
  state.selectedSource = state.selectedResult = null;
  state.kinds = [];
  renderPresets(); renderSources(); renderResults(); renderPreview(); renderCompare();
});

function renderSources() {
  const list = $('sourceList');
  list.innerHTML = '';
  const has = state.files.length > 0;
  show('sourcesEmpty', !has);
  show('sourcesFoot', has);
  show('clearBtn', has);
  setText($('sourceCount'), has ? String(state.files.length) : '');

  let total = 0;
  for (const file of state.files) {
    total += file.bytes || 0;
    const result = state.results[file.path];

    const row = document.createElement('li');
    row.className = 'file-row';
    row.setAttribute('aria-selected', String(state.selectedSource === file.path));
    row.tabIndex = 0;

    const name = document.createElement('div');
    name.className = 'file-name';
    name.textContent = file.name;
    row.append(name);

    const meta = document.createElement('div');
    meta.className = 'file-meta';
    const bits = [file.size, file.resolution, file.duration ? clockTime(file.duration) : ''].filter(Boolean);
    if (file.is_hdr) bits.push('HDR');
    if (file.has_alpha) bits.push('transparent');
    meta.textContent = bits.join('  ·  ');
    row.append(meta);

    if (result && result.status === 'running') {
      const label = document.createElement('div');
      label.className = 'file-meta state running';
      const pass = result.pass_count > 1 ? ` · pass ${result.pass_number}/${result.pass_count}` : '';
      const eta = result.eta > 0 ? ` · ${formatTime(result.eta)} left` : '';
      label.textContent = `${Math.round(result.fraction * 100)}%${pass}${eta}`;
      row.append(label);
      const track = document.createElement('div');
      track.className = 'track';
      const fill = document.createElement('div');
      fill.className = 'fill';
      fill.style.width = `${result.fraction * 100}%`;
      track.append(fill);
      row.append(track);
    } else if (result && result.status !== 'done') {
      const label = document.createElement('div');
      label.className = `file-meta state ${result.status}`;
      label.textContent = result.message || result.status;
      row.append(label);
    }

    const choose = () => {
      state.selectedSource = file.path;
      renderSources();
      switchTab('Preview');
      renderPreview();
    };
    row.addEventListener('click', choose);
    row.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); choose(); }
    });
    list.append(row);
  }
  setText($('sourcesTotal'), has ? `${state.files.length} file${state.files.length === 1 ? '' : 's'}, ${humanTotal(total)}` : '');

  const ready = has && !isRunning();
  $('startBtn').disabled = !ready;
  $('sampleBtn').disabled = !ready;
  $('bakeoffBtn').disabled = !ready;
}

const isRunning = () => Object.values(state.results).some((r) => r.status === 'running' || r.status === 'queued');

async function refreshSelection() {
  if (!state.paths.length) { state.files = []; state.kinds = []; renderPresets(); renderSources(); return; }
  setText($('actionHint'), 'Reading files...');
  let data;
  try {
    data = await post('/api/inspect', { paths: state.paths, recursive: $('recursive').checked, kinds: modeKinds() });
  } catch (error) {
    setText($('actionHint'), error.message);
    return;
  }

  // Every chosen file comes back. Only the first batch has been opened and
  // measured; the rest are listed from name and size, which is all this needs.
  state.files = data.details;
  state.kinds = data.kinds || [];

  if (data.needs_raw_decoder) {
    setText($('rawText'),
      'Some of these are camera RAW files and this computer has no RAW decoder installed. ' +
      'Install one and they will convert at full quality:');
    setText($('rawHint'), data.raw_install_hint || '');
    show('rawNotice', true);
  } else {
    show('rawNotice', false);
  }

  if (data.upgrade_offer) {
    setText($('upgradeText'),
      `${data.unreadable.length} file${data.unreadable.length === 1 ? '' : 's'} could not be opened by the installed ffmpeg. ` +
      'A newer build, downloaded into the VidSqueeze folder, will very likely read them.');
    show('upgradeOffer', true);
  } else {
    show('upgradeOffer', false);
  }

  const unmeasured = data.count - (data.probed || 0);
  setText($('actionHint'), unmeasured > 0
    ? `${data.count} files ready. The first ${data.probed} have been measured; the rest are read as they are converted.`
    : (data.problems || []).join(' '));

  renderPresets();
  renderSources();
}

/* ---------- results ---------- */

function renderResults() {
  const list = $('resultList');
  list.innerHTML = '';
  const done = Object.values(state.results).filter((r) => r.status === 'done');
  show('resultsEmpty', done.length === 0 && !isRunning());
  setText($('resultCount'), done.length ? String(done.length) : '');

  for (const item of done) {
    const row = document.createElement('li');
    row.className = 'file-row';
    row.setAttribute('aria-selected', String(state.selectedResult === item.path));
    row.tabIndex = 0;

    const name = document.createElement('div');
    name.className = 'file-name';
    name.textContent = item.output_name || item.name;
    row.append(name);

    const meta = document.createElement('div');
    meta.className = 'file-meta state done';
    meta.textContent = item.percent_saved > 0
      ? `${item.output_size}  ·  ${item.percent_saved}% smaller`
      : item.output_size;
    row.append(meta);

    if (item.replaced) {
      const note = document.createElement('div');
      note.className = 'file-meta';
      note.textContent = 'original deleted';
      row.append(note);
    }

    const choose = () => {
      state.selectedResult = item.path;
      renderResults();
      switchTab('Compare');
      renderCompare();
    };
    row.addEventListener('click', choose);
    row.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); choose(); }
    });
    list.append(row);
  }
}

$('openOutput').addEventListener('click', () => post('/api/reveal', { path: $('outputPath').textContent }));
$('revealBtn').addEventListener('click', () => post('/api/reveal', { path: $('outputPath').textContent }));

/* ---------- file browser ---------- */

$('browserClose').addEventListener('click', () => show('browser', false));

async function openBrowser(mode) {
  state.browserMode = mode;
  setText($('browserTitle'), mode === 'watch' ? 'Choose a folder to watch' : 'Choose files');
  $('addSelectedBtn').hidden = mode !== 'files';
  setText($('addFolderBtn'), mode === 'files' ? 'Use this folder' : 'Watch this folder');
  show('browser', true);
  const { places } = await api('/api/places');
  const list = $('placesList');
  list.innerHTML = '';
  for (const place of places) {
    const item = document.createElement('li');
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = place.name;
    button.title = place.path;
    button.addEventListener('click', () => loadFolder(place.path));
    item.append(button);
    list.append(item);
  }
  loadFolder(state.browserPath || places[0].path);
}

async function loadFolder(path) {
  const data = await api(`/api/browse?path=${encodeURIComponent(path)}${kindsParam()}`);
  if (data.error) { setText($('browserError'), data.error); show('browserError', true); return; }
  show('browserError', false);
  state.browserPath = data.path;
  setText($('currentPath'), data.path);
  $('upBtn').disabled = !data.parent;
  $('upBtn').onclick = () => data.parent && loadFolder(data.parent);

  const folders = $('folderList');
  folders.innerHTML = '';
  for (const folder of data.folders) {
    const item = document.createElement('li');
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = `\u{1F4C1}  ${folder.name}`;
    button.addEventListener('click', () => loadFolder(folder.path));
    item.append(button);
    folders.append(item);
  }

  const files = $('fileBrowseList');
  files.innerHTML = '';
  state.lastChecked = -1;

  if (state.browserMode === 'files') {
    data.files.forEach((file, index) => {
      const item = document.createElement('li');
      const label = document.createElement('label');
      const box = document.createElement('input');
      box.type = 'checkbox';
      box.value = file.path;
      box.dataset.index = String(index);
      // The click carries the modifier keys; the change event does not, so the
      // range has to be worked out here and the box left to toggle itself.
      box.addEventListener('click', (event) => handleBoxClick(event, index));
      box.addEventListener('change', updateAddButton);
      const name = document.createElement('span');
      name.className = 'fname';
      name.textContent = file.name;
      const size = document.createElement('span');
      size.className = 'fsize';
      size.textContent = file.size;
      label.append(box, name, size);
      item.append(label);
      files.append(item);
    });

    if (!data.folders.length && !data.files.length) {
      const empty = document.createElement('li');
      empty.className = 'muted tiny-text';
      empty.textContent = data.hidden
        ? `This folder has ${data.hidden} file${data.hidden === 1 ? '' : 's'}, but none of the kind you are working with.`
        : 'This folder has nothing VidSqueeze can open.';
      files.append(empty);
    }
  }

  const count = data.files.length;
  show('selectAllRow', state.browserMode === 'files' && count > 0);
  $('selectAll').checked = false;
  $('selectAll').indeterminate = false;
  setText($('browseCount'), count
    ? `${count} file${count === 1 ? '' : 's'}` + (data.hidden ? `, ${data.hidden} of other kinds hidden` : '')
    : '');
  updateAddButton();
}

/* Click, shift-click for a range, exactly as a file manager behaves. Uses only
   the standard shiftKey flag, so it works the same on every platform. */
function handleBoxClick(event, index) {
  const boxes = [...document.querySelectorAll('#fileBrowseList input[type=checkbox]')];
  if (event.shiftKey && state.lastChecked >= 0 && state.lastChecked !== index) {
    const wanted = event.target.checked;
    const [from, to] = [state.lastChecked, index].sort((a, b) => a - b);
    for (let i = from; i <= to; i += 1) boxes[i].checked = wanted;
  }
  state.lastChecked = index;
  updateAddButton();
}

const checkedFiles = () => [...document.querySelectorAll('#fileBrowseList input:checked')].map((i) => i.value);
function updateAddButton() {
  const boxes = [...document.querySelectorAll('#fileBrowseList input[type=checkbox]')];
  const chosen = boxes.filter((b) => b.checked).length;
  $('addSelectedBtn').disabled = chosen === 0;
  setText($('addSelectedBtn'), chosen ? `Add ${chosen} selected` : 'Add selected');
  const all = $('selectAll');
  if (all) {
    all.checked = chosen > 0 && chosen === boxes.length;
    all.indeterminate = chosen > 0 && chosen < boxes.length;
  }
}

$('selectAll').addEventListener('change', (event) => {
  for (const box of document.querySelectorAll('#fileBrowseList input[type=checkbox]')) {
    box.checked = event.target.checked;
  }
  state.lastChecked = -1;
  updateAddButton();
});

$('addSelectedBtn').addEventListener('click', () => { addPaths(checkedFiles()); show('browser', false); });
$('addFolderBtn').addEventListener('click', () => {
  if (!state.browserPath) return;
  if (state.browserMode === 'watch') {
    state.watchFolder = state.browserPath;
    setText($('watchPath'), state.watchFolder);
    $('watchStart').disabled = false;
  } else {
    addPaths([state.browserPath]);
  }
  show('browser', false);
});

function addPaths(paths) {
  for (const path of paths) if (!state.paths.includes(path)) state.paths.push(path);
  refreshSelection();
}

/* ---------- preview and trim ---------- */

async function renderPreview() {
  const path = state.selectedSource;
  const file = state.files.find((f) => f.path === path);
  show('previewEmpty', !file);
  show('previewBody', !!file);
  if (!file) return;

  setText($('previewName'), file.name);
  setText($('previewMeta'), file.summary || '');

  const stage = $('previewStage');
  stage.innerHTML = '';
  const kind = file.kind || 'video';

  if (kind === 'image') {
    const img = document.createElement('img');
    img.src = mediaUrl(path);
    img.alt = file.name;
    stage.append(img);
  } else if (file.playable) {
    const player = document.createElement(kind === 'audio' ? 'audio' : 'video');
    player.src = mediaUrl(path);
    player.controls = true;
    player.preload = 'metadata';
    stage.append(player);
  } else {
    const note = document.createElement('div');
    note.className = 'placeholder';
    note.textContent = 'Your browser cannot play this format. Use Open below, or the frame view after converting.';
    stage.append(note);
    if (kind === 'video') {
      const still = document.createElement('img');
      still.src = frameUrl(path, (file.duration || 0) * 0.33, 800);
      stage.append(still);
    }
  }

  const trimmable = kind === 'video' && (file.duration || 0) > 1;
  show('trimBlock', trimmable);
  if (trimmable) {
    state.duration = file.duration;
    buildFilmstrip(path, file.duration);
    $('trimStartRange').value = '0';
    $('trimEndRange').value = '1000';
    updateTrimReadout();
  }
}

function buildFilmstrip(path, duration) {
  const strip = $('filmstrip');
  strip.innerHTML = '';
  const count = 8;
  for (let i = 0; i < count; i += 1) {
    const at = duration * ((i + 0.5) / count);
    const img = document.createElement('img');
    img.loading = 'lazy';
    img.alt = '';
    img.src = frameUrl(path, at, 220);
    strip.append(img);
  }
}

function trimSeconds() {
  const start = (Number($('trimStartRange').value) / 1000) * state.duration;
  const end = (Number($('trimEndRange').value) / 1000) * state.duration;
  return [Math.min(start, end), Math.max(start, end)];
}
function updateTrimReadout() {
  const [start, end] = trimSeconds();
  setText($('trimReadout'), `${clockTime(start)} to ${clockTime(end)}  ·  keeps ${clockTime(end - start)}`);
}
$('trimStartRange').addEventListener('input', updateTrimReadout);
$('trimEndRange').addEventListener('input', updateTrimReadout);

$('trimApply').addEventListener('click', () => {
  const [start, end] = trimSeconds();
  $('trimStart').value = start > 0.05 ? start.toFixed(1) : '';
  $('trimEnd').value = end < state.duration - 0.05 ? end.toFixed(1) : '';
  switchTab('Settings');
  setText($('actionHint'), `Trim set to ${clockTime(start)} - ${clockTime(end)}. It applies to every file in the batch.`);
});
$('trimReset').addEventListener('click', () => {
  $('trimStartRange').value = '0';
  $('trimEndRange').value = '1000';
  $('trimStart').value = '';
  $('trimEnd').value = '';
  updateTrimReadout();
});

/* ---------- running ---------- */

$('startBtn').addEventListener('click', async () => {
  const replacing = $('replaceOriginals').checked;
  if (replacing && !window.confirm(
    `Delete ${state.files.length} original file(s) after converting?\n\n` +
    'Each original is only deleted once the new file passes every check. This cannot be undone.'
  )) return;

  $('startBtn').disabled = true;
  try {
    await post('/api/queue/start', {
      paths: state.paths,
      recursive: $('recursive').checked,
      kinds: modeKinds(),
      spec: readSpec(),
      replace_originals: replacing,
      concurrency: $('concurrency').checked ? 2 : 1,
      preset: state.activePreset,
    });
  } catch (error) {
    setText($('actionHint'), error.message);
    renderSources();
    return;
  }
  post('/api/settings', {
    replace_originals: replacing,
    concurrency: $('concurrency').checked ? 2 : 1,
    recursive: $('recursive').checked,
  }).catch(() => {});
  show('cancelBtn', true);
  show('resultsFoot', true);
  startPolling();
});

$('cancelBtn').addEventListener('click', async () => {
  $('cancelBtn').disabled = true;
  await post('/api/queue/cancel').catch(() => {});
});

function startPolling() {
  clearInterval(state.polling);
  state.polling = setInterval(pollQueue, 600);
  pollQueue();
}

async function pollQueue() {
  let snapshot;
  try { snapshot = await api('/api/queue'); } catch { return; }

  const known = new Set(state.files.map((f) => f.path));
  for (const item of snapshot.items || []) {
    state.results[item.path] = item;
    if (!known.has(item.path)) {
      state.files.push({ path: item.path, name: item.name, size: item.source_size, bytes: item.source_bytes });
      known.add(item.path);
    }
  }

  const totals = snapshot.totals || {};
  const bar = $('overallBar');
  if (bar) bar.style.width = `${(totals.overall_fraction || 0) * 100}%`;
  setText($('resultsTotal'), totals.total
    ? `${totals.completed || 0} of ${totals.total} done` +
      (totals.running && totals.eta > 0 ? `, about ${formatTime(totals.eta)} left` : '') +
      (totals.saved_bytes > 0 ? `  ·  ${totals.saved_size} saved` : '')
    : '');
  show('resultsFoot', !!totals.total);

  renderSources();
  renderResults();

  const finished = totals.total && !totals.running && totals.completed >= totals.total;
  if (finished) {
    clearInterval(state.polling);
    show('cancelBtn', false);
    $('cancelBtn').disabled = false;
    setText($('actionHint'), `Finished. ${totals.saved_size} saved.`);
    api('/api/history').then(renderHistory).catch(() => {});
    if (!state.selectedResult) {
      const first = (snapshot.items || []).find((i) => i.status === 'done');
      if (first) { state.selectedResult = first.path; renderResults(); switchTab('Compare'); renderCompare(); }
    }
  }
}

/* ---------- sample and bake-off ---------- */

function sampleTarget() {
  return state.selectedSource || (state.files[0] && state.files[0].path);
}

async function runSample(candidates, title, intro) {
  const target = sampleTarget();
  if (!target) return;
  show('sampleModal', true);
  show('sampleProgress', true);
  show('sampleError', false);
  $('sampleResults').innerHTML = '';
  setText($('sampleTitle'), title);
  setText($('sampleIntro'), intro.replace('{name}', target.split(/[\\/]/).pop()));
  setText($('sampleMessage'), 'Working. This usually takes well under a minute.');

  try {
    await post('/api/sample/start', { path: target, spec: readSpec(), seconds: 8, candidates });
  } catch (error) {
    setText($('sampleError'), error.message);
    show('sampleError', true);
    show('sampleProgress', false);
    return;
  }
  clearInterval(state.samplePolling);
  state.samplePolling = setInterval(async () => {
    const status = await api('/api/sample').catch(() => null);
    if (!status) return;
    renderSamples(status);
    if (!status.running) {
      clearInterval(state.samplePolling);
      show('sampleProgress', false);
      if (status.error) { setText($('sampleError'), status.error); show('sampleError', true); }
    }
  }, 800);
}

$('sampleBtn').addEventListener('click', () => {
  runSample([{ preset: state.activePreset }], 'Sample test',
    'Converting a short stretch of {name} with your current settings, to show what the whole file would come to.');
});

$('bakeoffBtn').addEventListener('click', () => {
  const kinds = new Set(state.kinds);
  const options = kinds.has('image') && !kinds.has('video')
    ? ['photo_web', 'photo_webp', 'photo_avif']
    : ['high_quality', 'balanced', 'small'];
  const candidates = options.filter((k) => state.presets.some((p) => p.key === k)).map((k) => ({ preset: k }));
  runSample(candidates, 'Try several settings',
    'Converting a short stretch of {name} at each setting, so you can pick before committing to the whole file.');
});

function renderSamples(status) {
  const host = $('sampleResults');
  host.innerHTML = '';
  for (const result of status.results || []) {
    const card = document.createElement('div');
    card.className = 'sample-card';
    const info = document.createElement('div');
    info.className = 'info';
    const title = document.createElement('strong');
    title.textContent = result.label;
    info.append(title);

    const est = document.createElement('div');
    est.className = 'est';
    if (result.ok) {
      const size = document.createElement('b');
      size.textContent = result.estimated_size;
      const time = document.createElement('b');
      time.textContent = formatTime(result.estimated_seconds);
      info.append(est);
      if (result.exact) {
        // A still was converted whole, so this is the result, not a guess.
        est.append('Comes out at ', size, ', in ', time);
      } else {
        est.append('Whole file would be about ', size, ', taking roughly ', time);
      }
    } else {
      est.textContent = result.message || 'This setting failed.';
      info.append(est);
    }
    if (result.ok && result.message) {
      const note = document.createElement('div');
      note.className = 'est';
      note.textContent = result.message;
      info.append(note);
    }
    card.append(info);

    if (result.ok) {
      const use = document.createElement('button');
      use.type = 'button';
      use.className = 'btn secondary tiny';
      use.textContent = 'Use this';
      use.addEventListener('click', () => { selectPreset(result.key); show('sampleModal', false); });
      card.append(use);
    }
    host.append(card);
  }
}

$('sampleClose').addEventListener('click', () => {
  clearInterval(state.samplePolling);
  show('sampleModal', false);
});

/* ---------- watch folder ---------- */

$('watchPick').addEventListener('click', () => openBrowser('watch'));

$('watchStart').addEventListener('click', async () => {
  try {
    await post('/api/watch/start', {
      folder: state.watchFolder,
      recursive: $('watchRecursive').checked,
      include_existing: $('watchExisting').checked,
    });
  } catch (error) {
    setText($('watchStatus'), error.message);
    return;
  }
  show('watchStop', true);
  $('watchStart').disabled = true;
  clearInterval(state.watchPolling);
  state.watchPolling = setInterval(pollWatch, 2500);
  pollWatch();
});

$('watchStop').addEventListener('click', async () => {
  await post('/api/watch/stop').catch(() => {});
  clearInterval(state.watchPolling);
  show('watchStop', false);
  $('watchStart').disabled = false;
  setText($('watchStatus'), 'Stopped watching.');
});

async function pollWatch() {
  const status = await api('/api/watch').catch(() => null);
  if (!status) return;
  if (status.found && status.found.length) {
    addPaths(status.found);
    setText($('watchStatus'),
      `Watching ${status.folder}. Added ${status.found.length} new file${status.found.length === 1 ? '' : 's'}.`);
  } else if (status.watching) {
    setText($('watchStatus'),
      `Watching ${status.folder}.` + (status.settling ? ` ${status.settling} file(s) still copying.` : ' Nothing new.'));
  }
  if (status.error) setText($('watchStatus'), status.error);
}

/* ---------- compare ---------- */

const tabs = {
  Settings: 'tabSettings', Preview: 'tabPreview', Compare: 'tabCompare',
  Watch: 'tabWatch', History: 'tabHistory',
};
for (const name of Object.keys(tabs)) {
  $(`tabBtn${name}`).addEventListener('click', () => switchTab(name));
}
function switchTab(name) {
  for (const [other, panel] of Object.entries(tabs)) {
    const active = other === name;
    $(`tabBtn${other}`).setAttribute('aria-selected', String(active));
    show(panel, active);
  }
  if (name === 'Compare') renderCompare();
  if (name === 'Preview') renderPreview();
}

async function renderCompare() {
  const result = state.selectedResult ? state.results[state.selectedResult] : null;
  const usable = result && result.status === 'done' && result.output;
  show('compareEmpty', !usable);
  show('compareBody', !!usable);
  if (!usable) return;

  setText($('compareName'), result.name);
  setText($('compareRatio'), result.ratio ? `${result.ratio}x` : `${result.percent_saved}%`);
  setText($('sizeBefore'), result.source_size);
  setText($('sizeAfter'), result.output_size);
  const widest = Math.max(result.source_bytes, result.output_bytes) || 1;
  $('barBefore').style.width = `${(result.source_bytes / widest) * 100}%`;
  $('barAfter').style.width = `${(result.output_bytes / widest) * 100}%`;

  let described;
  try {
    described = await post('/api/describe', { paths: [state.selectedResult, result.output] });
  } catch { return; }
  const [before, after] = described.files;
  if (!before || !after) return;
  state.duration = before.duration || 0;

  buildCompareModes(before, after);
  renderFacts(before, after);
  buildPlayers(before, after, result);

  const framesPossible = (before.kind !== 'audio') && (after.kind !== 'audio');
  if (framesPossible) updateFrames();

  $('openBefore').onclick = () => post('/api/open', { path: state.selectedResult }).catch(() => {});
  $('openAfter').onclick = () => post('/api/open', { path: result.output }).catch(() => {});
}

function buildCompareModes(before, after) {
  const host = $('compareModeBtns');
  host.innerHTML = '';
  const framesPossible = before.kind !== 'audio' && after.kind !== 'audio';
  const modes = [];
  if (framesPossible) modes.push(['frames', before.kind === 'image' ? 'Images' : 'Frames']);
  modes.push(['play', before.kind === 'audio' ? 'Listen' : 'Play']);

  if (!framesPossible) state.compareMode = 'play';
  if (!modes.some(([v]) => v === state.compareMode)) state.compareMode = modes[0][0];

  for (const [value, label] of modes) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'seg';
    button.textContent = label;
    button.setAttribute('aria-pressed', String(state.compareMode === value));
    button.addEventListener('click', () => {
      state.compareMode = value;
      for (const other of host.querySelectorAll('.seg')) {
        other.setAttribute('aria-pressed', String(other === button));
      }
      show('frameMode', value === 'frames');
      show('playMode', value === 'play');
      if (value === 'frames') updateFrames();
    });
    host.append(button);
  }
  show('frameMode', state.compareMode === 'frames');
  show('playMode', state.compareMode === 'play');
  show('frameScrub', before.kind !== 'image');
}

/* Play whichever side the browser can manage. If both work they can be run
   together; if only one does, that one is still playable and the other is a
   button away in the user's own program. */
function buildPlayers(before, after, result) {
  const host = $('playPair');
  host.innerHTML = '';
  const sides = [
    { label: 'Original', info: before, path: state.selectedResult },
    { label: 'New', info: after, path: result.output },
  ];

  for (const side of sides) {
    const figure = document.createElement('figure');
    const caption = document.createElement('figcaption');
    caption.textContent = side.label;
    figure.append(caption);

    if (side.info.kind === 'image') {
      const img = document.createElement('img');
      img.src = mediaUrl(side.path);
      img.alt = side.label;
      img.style.width = '100%';
      img.style.borderRadius = '7px';
      figure.append(img);
    } else if (side.info.playable) {
      const player = document.createElement(side.info.kind === 'audio' ? 'audio' : 'video');
      player.src = mediaUrl(side.path);
      player.controls = true;
      player.preload = 'metadata';
      player.dataset.side = side.label;
      if (side.info.kind === 'audio') player.style.width = '100%';
      figure.append(player);
    } else {
      const note = document.createElement('div');
      note.className = 'placeholder';
      note.style.cssText = 'border:1px solid var(--line);border-radius:7px;padding:22px 14px;text-align:center';
      note.textContent = `Your browser cannot play this ${side.info.codec || 'format'}.`;
      const open = document.createElement('button');
      open.type = 'button';
      open.className = 'btn secondary tiny';
      open.style.marginTop = '8px';
      open.textContent = `Open ${side.label.toLowerCase()}`;
      open.addEventListener('click', () => post('/api/open', { path: side.path }).catch(() => {}));
      note.append(document.createElement('br'), open);
      figure.append(note);
    }
    host.append(figure);
  }

  const players = host.querySelectorAll('video, audio');
  const both = players.length === 2;
  show('syncPlay', both);
  show('syncPause', both);
  setText($('playWarn'), both
    ? ''
    : (players.length === 1
      ? 'Only one of these plays in the browser, so they cannot be run side by side. The other opens in your own player.'
      : 'Neither format plays in the browser. Use the buttons above to open them in your own player.'));
}

$('syncPlay').addEventListener('click', () => {
  const players = $('playPair').querySelectorAll('video, audio');
  if (players.length < 2) return;
  const [a, b] = players;
  b.currentTime = a.currentTime;
  a.play(); b.play();
});
$('syncPause').addEventListener('click', () => {
  for (const player of $('playPair').querySelectorAll('video, audio')) player.pause();
});

function renderFacts(before, after) {
  const body = $('factsBody');
  body.innerHTML = '';
  const rows = [['Size', before.size, after.size],
                ['Dimensions', `${before.width}x${before.height}`, `${after.width}x${after.height}`],
                ['Format', before.codec || '-', after.codec || '-']];
  if (before.kind !== 'image') {
    rows.push(['Audio', before.audio_codec || 'none', after.audio_codec || 'none']);
    rows.push(['Bitrate', `${Math.round((before.bitrate || 0) / 1000)} kbps`, `${Math.round((after.bitrate || 0) / 1000)} kbps`]);
    rows.push(['Length', clockTime(before.duration), clockTime(after.duration)]);
  }
  if (before.has_alpha || after.has_alpha) {
    rows.push(['Transparency', before.has_alpha ? 'yes' : 'no', after.has_alpha ? 'yes' : 'no']);
  }
  for (const [label, a, b] of rows) {
    const tr = document.createElement('tr');
    for (const value of [label, a, b]) {
      const td = document.createElement('td');
      td.textContent = value;
      tr.append(td);
    }
    body.append(tr);
  }
}

let frameToken = 0;
function updateFrames() {
  const result = state.results[state.selectedResult];
  if (!result || !result.output) return;
  const file = state.files.find((f) => f.path === state.selectedResult);
  const isImage = file && file.kind === 'image';
  const when = isImage ? 0 : state.duration * (Number($('frameTime').value) / 100);
  setText($('frameTimeLabel'), clockTime(when));

  const mine = ++frameToken;
  show('frameLoading', true);
  let pending = 2;
  const settle = () => {
    if (mine !== frameToken) return;
    pending -= 1;
    if (pending <= 0) show('frameLoading', false);
  };
  const beforeImg = $('frameBefore');
  const afterImg = $('frameAfter');
  beforeImg.onload = beforeImg.onerror = settle;
  afterImg.onload = afterImg.onerror = settle;
  beforeImg.src = frameUrl(state.selectedResult, when, 900);
  afterImg.src = frameUrl(result.output, when, 900);
}

$('frameTime').addEventListener('input', () => {
  setText($('frameTimeLabel'), clockTime(state.duration * (Number($('frameTime').value) / 100)));
});
$('frameTime').addEventListener('change', updateFrames);

(function wireWipe() {
  const stage = $('frameStage');
  const clip = $('frameBeforeWrap');
  const handle = $('frameHandle');
  let dragging = false;

  const place = (clientX) => {
    const box = stage.getBoundingClientRect();
    const ratio = Math.min(1, Math.max(0, (clientX - box.left) / box.width));
    clip.style.clipPath = `inset(0 ${(1 - ratio) * 100}% 0 0)`;
    handle.style.left = `${ratio * 100}%`;
  };
  const start = (e) => { dragging = true; place(e.clientX ?? e.touches[0].clientX); };
  const move = (e) => {
    if (!dragging) return;
    if (e.cancelable) e.preventDefault();
    place(e.clientX ?? e.touches[0].clientX);
  };
  const stop = () => { dragging = false; };

  stage.addEventListener('mousedown', start);
  stage.addEventListener('touchstart', start, { passive: true });
  window.addEventListener('mousemove', move);
  window.addEventListener('touchmove', move, { passive: false });
  window.addEventListener('mouseup', stop);
  window.addEventListener('touchend', stop);

  stage.tabIndex = 0;
  stage.addEventListener('keydown', (event) => {
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
    event.preventDefault();
    const current = parseFloat(handle.style.left) || 50;
    const next = Math.min(100, Math.max(0, current + (event.key === 'ArrowRight' ? 4 : -4)));
    clip.style.clipPath = `inset(0 ${100 - next}% 0 0)`;
    handle.style.left = `${next}%`;
  });
})();

/* ---------- history ---------- */

function renderHistory(data) {
  if (!data) return;
  setText($('historyTotal'), data.total_saved);
  setText($('historyCount'), `${data.count} file${data.count === 1 ? '' : 's'}`);

  const chip = $('lifetimeSaved');
  if (data.total_saved_bytes > 0) { setText(chip, `${data.total_saved} saved`); chip.hidden = false; }
  else chip.hidden = true;

  const list = $('historyList');
  list.innerHTML = '';
  show('historyEmpty', !data.recent.length);
  for (const entry of data.recent) {
    const item = document.createElement('li');
    const name = document.createElement('span');
    name.className = 'hname';
    name.textContent = entry.name;
    name.title = entry.source;
    const saved = document.createElement('span');
    saved.className = 'hsave';
    saved.textContent = `${entry.percent_saved}%`;
    const detail = document.createElement('span');
    detail.className = 'hago';
    detail.textContent = `${entry.source_size} → ${entry.output_size}  ·  ${entry.ago}`;
    item.append(name, saved, detail);
    list.append(item);
  }
}

$('historyClear').addEventListener('click', async () => {
  if (!window.confirm('Clear the history? This only removes the record, not any files.')) return;
  await post('/api/history/clear').catch(() => {});
  renderHistory(await api('/api/history').catch(() => null));
});

/* ---------- updates ---------- */

$('updatesBtn').addEventListener('click', () => openUpdates(false));
$('updatesClose').addEventListener('click', () => show('updatesModal', false));
$('updatesRecheck').addEventListener('click', () => openUpdates(true));

async function openUpdates(force) {
  show('updatesModal', true);
  show('updatesError', false);
  $('updatesBody').innerHTML = '<p class="muted tiny-text">Checking...</p>';
  let report;
  try {
    report = await api(`/api/updates${force ? '?force=1' : ''}`);
  } catch (error) {
    $('updatesBody').innerHTML = '';
    setText($('updatesError'), error.message);
    show('updatesError', true);
    return;
  }
  renderUpdates(report);
}

function renderUpdates(report) {
  const host = $('updatesBody');
  host.innerHTML = '';
  const app = report.app || {};
  const ff = report.ffmpeg || {};

  const self_ = report.self || {};
  host.append(updateRow({
    title: 'VidSqueeze',
    detail: (app.checked
      ? (app.update_available
        ? `You have ${app.current}. Version ${app.latest} is available.`
        : `You have ${app.current}, which is the newest.`)
      : `You have ${app.current}. No published version to compare against yet.`)
      + (app.update_available && self_.explanation ? ' ' + self_.explanation : ''),
    stale: !!app.update_available,
    action: app.update_available
      ? (self_.can_update
        ? { label: 'Update now', onClick: runSelfUpdate }
        : { label: 'How to update', href: app.url })
      : null,
  }));

  host.append(updateRow({
    title: 'ffmpeg',
    detail: ff.checked
      ? (ff.update_available
        ? `You have ${ff.current}. Version ${ff.latest} is available.` +
          (ff.replaces_system
            ? ' Yours came with the system, so a newer copy would be downloaded into the VidSqueeze folder and used instead.'
            : '')
        : `You have ${ff.current}, which is current.`)
      : `You have ${ff.current || 'none'}. Could not reach the download servers.`,
    stale: !!ff.update_available,
    action: ff.update_available ? { label: 'Update ffmpeg', onClick: runFfmpegUpdate } : null,
  }));

  $('updateDot').hidden = !(app.update_available || ff.update_available);

  const when = report.checked_at ? new Date(report.checked_at * 1000) : null;
  setText($('updatesChecked'), when
    ? `Last checked ${when.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`
    : '');
}

function updateRow({ title, detail, stale, action }) {
  const row = document.createElement('div');
  row.className = stale ? 'update-row stale' : 'update-row';
  const info = document.createElement('div');
  info.className = 'info';
  const strong = document.createElement('strong');
  strong.textContent = title;
  const text = document.createElement('div');
  text.className = 'detail';
  text.textContent = detail;
  info.append(strong, text);
  row.append(info);

  if (action) {
    if (action.href) {
      const link = document.createElement('a');
      link.className = 'btn secondary tiny';
      link.href = action.href;
      link.target = '_blank';
      link.rel = 'noopener';
      link.textContent = action.label;
      row.append(link);
    } else {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'btn primary tiny';
      button.textContent = action.label;
      button.addEventListener('click', () => action.onClick(button));
      row.append(button);
    }
  }
  return row;
}

async function runSelfUpdate(button) {
  if (!window.confirm(
    'Update VidSqueeze to the newest version?\n\n' +
    'Your converted files, settings and history are untouched, and the current ' +
    'version is kept so it can be put back.'
  )) return;

  button.disabled = true;
  show('updateProgress', true);
  show('updatesError', false);
  setText($('updateMessage'), 'Starting');
  try {
    await post('/api/updates/self');
  } catch (error) {
    setText($('updatesError'), error.message);
    show('updatesError', true);
    button.disabled = false;
    return;
  }

  const timer = setInterval(async () => {
    const status = await api('/api/updates/self').catch(() => null);
    if (!status) return;
    setText($('updateMessage'), status.message || '');
    $('updateBar').style.width = status.fraction >= 0 ? `${status.fraction * 100}%` : '100%';
    if (status.error) {
      clearInterval(timer);
      setText($('updatesError'), status.error);
      show('updatesError', true);
      button.disabled = false;
    } else if (!status.running && status.done) {
      clearInterval(timer);
      show('updateProgress', false);
      // The running program is the old one until it is started again, so there
      // is nothing useful left to do in this tab.
      $('updatesBody').innerHTML = '';
      const done = document.createElement('div');
      done.className = 'update-row stale';
      const info = document.createElement('div');
      info.className = 'info';
      const strong = document.createElement('strong');
      strong.textContent = 'Updated';
      const detail = document.createElement('div');
      detail.className = 'detail';
      detail.textContent = status.result +
        ' Close this window, stop VidSqueeze in the window it opened from, and start it again.';
      info.append(strong, detail);
      done.append(info);
      $('updatesBody').append(done);
    }
  }, 700);
}

async function runFfmpegUpdate(button) {
  button.disabled = true;
  show('updateProgress', true);
  setText($('updateMessage'), 'Starting');
  try {
    await post('/api/upgrade');
  } catch (error) {
    setText($('updatesError'), error.message);
    show('updatesError', true);
    button.disabled = false;
    return;
  }
  const timer = setInterval(async () => {
    const status = await api('/api/setup').catch(() => null);
    if (!status) return;
    setText($('updateMessage'), status.message || '');
    $('updateBar').style.width = status.fraction >= 0 ? `${status.fraction * 100}%` : '100%';
    if (status.error) {
      clearInterval(timer);
      setText($('updatesError'), status.error);
      show('updatesError', true);
      button.disabled = false;
    } else if (!status.running && status.done) {
      clearInterval(timer);
      show('updateProgress', false);
      await boot();
      openUpdates(true);
    }
  }, 600);
}

/* ---------- odds and ends ---------- */

$('quitBtn').addEventListener('click', async () => {
  if (!window.confirm('Quit VidSqueeze? Anything still running will be stopped.')) return;
  await post('/api/quit').catch(() => {});
  document.body.innerHTML =
    '<div class="centre-screen"><div class="panel"><h1 class="display">Closed</h1><p class="muted">You can close this tab.</p></div></div>';
});

document.addEventListener('keydown', (event) => {
  if (event.key !== 'Escape') return;
  if (!$('browser').hidden) show('browser', false);
  else if (!$('updatesModal').hidden) show('updatesModal', false);
  else if (!$('sampleModal').hidden) { clearInterval(state.samplePolling); show('sampleModal', false); }
});

boot();
