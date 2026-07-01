'use strict';

// ====================================================================
// Communicatie dashboard — frontend (vanilla JS, geen build-stap)
// Telefonie + E-mailadressen, alles gelinkt aan de centrale lijsten
// (personen / firma's / afdelingen / leveranciers) uit kern.
// ====================================================================

const state = {
  refs: { personen: [], firmas: [], afdelingen: [], leveranciers: [], lijsten: {} },
  numbers: [],
  emails: [],
  stats: { total: 0, actief: 0, niet_actief: 0, onbekend: 0, dubbel: 0, probleem: 0 },
  filters: { land: '', status: '', firma: [], leverancier: '', q: '', duplicates: false, attention: false },
  emailFilters: { q: '', open: false },
  selectedId: null,
};

const $ = (sel) => document.querySelector(sel);
const el = (tag, props = {}, ...children) => {
  const node = document.createElement(tag);
  Object.entries(props).forEach(([k, v]) => {
    if (k === 'class') node.className = v;
    else if (k === 'html') node.innerHTML = v;
    else if (k.startsWith('on') && typeof v === 'function') node.addEventListener(k.slice(2), v);
    else if (v !== null && v !== undefined) node.setAttribute(k, v);
  });
  children.flat().forEach((c) => {
    if (c === null || c === undefined) return;
    node.append(c.nodeType ? c : document.createTextNode(String(c)));
  });
  return node;
};

// ---- API helper ----------------------------------------------------
async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  let data = null;
  const ct = res.headers.get('content-type') || '';
  if (ct.includes('application/json')) data = await res.json();
  if (!res.ok) throw Object.assign(new Error((data && data.error) || 'Fout'), { data, status: res.status });
  return data;
}

// ---- Toast ---------------------------------------------------------
let toastTimer;
function toast(msg, isError = false) {
  const t = $('#toast');
  t.textContent = msg;
  t.className = 'toast show' + (isError ? ' err' : '');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (t.className = 'toast'), 2600);
}

// ---- Helpers -------------------------------------------------------
const STATUSES = ['Actief', 'Niet-actief', 'Onbekend'];
function statusClass(s) {
  if (s === 'Actief') return 'actief';
  if (s === 'Niet-actief') return 'nietactief';
  return 'onbekend';
}
function statusBadge(s) {
  return el('span', { class: 'badge ' + statusClass(s) }, s || 'Onbekend');
}
function esc(s) {
  return String(s ?? '');
}
function lijstWaarden(cat) {
  return (state.refs.lijsten[cat] || []).map((x) => x.waarde);
}

// Link naar het medewerkersprofiel (medewerkers.<domein>/<persoon_id>).
function profileUrl(persoonId) {
  const parts = location.hostname.split('.');
  parts[0] = 'organisatie';
  return `${location.protocol}//${parts.join('.')}/${persoonId}`;
}
function persoonLink(persoonId, naam) {
  if (!persoonId) return el('span', { class: 'muted' }, '—');
  return el('a', {
    class: 'person-link',
    href: profileUrl(persoonId),
    target: '_blank',
    rel: 'noopener',
    title: 'Open profiel in Medewerkers',
    onclick: (e) => e.stopPropagation(),
  }, naam || 'profiel');
}

// Bepaal of/waarom een rij nazicht vraagt.
function rowFlag(n) {
  if (n.is_duplicate) return { type: 'dup', label: 'Duplicaat nummer', amber: false, tip: n.aandacht || 'Dit nummer komt meermaals voor.' };
  const a = (n.aandacht || '').trim();
  if (!a) return null;
  const low = a.toLowerCase();
  let label = 'Controleren';
  if (low.includes('ontbreekt')) label = 'Nummer ontbreekt';
  else if (low.includes('onbekend')) label = 'Status onbekend';
  return { type: 'attn', label, amber: true, tip: a };
}

// ====================================================================
// KPI-kaarten
// ====================================================================
function resetFilters(f) {
  f.status = ''; f.duplicates = false; f.attention = false;
  f.land = ''; f.firma = []; f.leverancier = ''; f.q = '';
}

const KPI_DEFS = [
  { key: 'total', cls: 'k-total', icon: 'phone', label: 'Totaal nummers', sub: 'Alle geregistreerde nummers',
    value: (s) => s.total,
    active: (f) => !f.status && !f.duplicates && !f.attention && !f.land && !f.firma.length && !f.leverancier,
    apply: (f) => { resetFilters(f); } },
  { key: 'actief', cls: 'k-actief', icon: 'check', label: 'Actief', sub: 'Momenteel in gebruik',
    value: (s) => s.actief,
    active: (f) => f.status === 'Actief',
    apply: (f) => { const on = f.status === 'Actief'; f.status = on ? '' : 'Actief'; f.duplicates = false; f.attention = false; } },
  { key: 'dubbel', cls: 'k-dubbel', icon: 'warning', label: 'Duplicaat / conflict', sub: 'Vereist actie',
    value: (s) => s.dubbel,
    active: (f) => f.duplicates,
    apply: (f) => { const on = f.duplicates; f.duplicates = !on; f.attention = false; f.status = ''; } },
  { key: 'onbekend', cls: 'k-onbekend', icon: 'question', label: 'Onbekend', sub: 'Status onbekend',
    value: (s) => s.onbekend,
    active: (f) => f.status === 'Onbekend',
    apply: (f) => { const on = f.status === 'Onbekend'; f.status = on ? '' : 'Onbekend'; f.duplicates = false; f.attention = false; } },
];

function renderKpis() {
  const wrap = $('#kpis');
  wrap.innerHTML = '';
  KPI_DEFS.forEach((def) => {
    wrap.append(
      el('button', {
        class: 'kpi ' + def.cls + (def.active(state.filters) ? ' active' : ''),
        onclick: () => {
          def.apply(state.filters);
          renderFilters();
          renderKpis();
          load();
        },
      },
        el('div', { class: 'kpi-label' }, def.label),
        el('div', { class: 'kpi-value' }, String(def.value(state.stats)))
      )
    );
  });
}

// ====================================================================
// Filters (chips uit de centrale lijsten)
// ====================================================================
function chipRow(container, items, current, onPick) {
  container.innerHTML = '';
  items.forEach((it) => {
    container.append(
      el('button', {
        class: 'chip' + (current === it.value ? ' active' : ''),
        title: it.title || null,
        onclick: () => onPick(current === it.value ? '' : it.value),
      }, it.label)
    );
  });
}

function renderFilters() {
  const f = state.filters;
  const rerun = () => { renderFilters(); renderKpis(); load(); };

  chipRow($('#landChips'),
    [{ value: '', label: 'Alles' }, ...lijstWaarden('Land').map((l) => ({ value: l, label: l }))],
    f.land, (v) => { f.land = v; rerun(); });

  chipRow($('#statusChips'),
    [{ value: '', label: 'Alles' }, ...STATUSES.map((s) => ({ value: s, label: s }))],
    f.status, (v) => { f.status = v; f.duplicates = false; f.attention = false; rerun(); });

  // Firma: multi-select — meerdere chips tegelijk aan te zetten.
  const fc = $('#firmaChips');
  fc.innerHTML = '';
  fc.append(el('button', {
    class: 'chip' + (f.firma.length === 0 ? ' active' : ''),
    onclick: () => { f.firma = []; rerun(); },
  }, 'Alles'));
  state.refs.firmas.forEach((x) => {
    const aan = f.firma.includes(x.id);
    fc.append(el('button', {
      class: 'chip' + (aan ? ' active' : ''),
      onclick: () => {
        f.firma = aan ? f.firma.filter((id) => id !== x.id) : [...f.firma, x.id];
        rerun();
      },
    }, x.naam));
  });

  chipRow($('#leverancierChips'),
    [{ value: '', label: 'Alles' }, ...state.refs.leveranciers.filter((l) => l.actief).map((x) => ({ value: x.id, label: x.naam }))],
    f.leverancier, (v) => { f.leverancier = v; rerun(); });
}

// ====================================================================
// Lijstweergave (tabel)
// ====================================================================
function renderTable() {
  const tbody = $('#rows');
  tbody.innerHTML = '';
  const rows = state.numbers;
  $('#emptyState').style.display = rows.length ? 'none' : 'block';

  rows.forEach((n) => {
    const flag = rowFlag(n);
    const tr = el('tr', { class: flag ? 'flagged' : '' });
    tr.append(
      el('td', { class: 'phone-cell' },
        el('div', { class: 'phone-line' },
          el('a', {
            class: 'person-link',
            href: '#',
            title: 'Alle informatie van dit nummer',
            onclick: (e) => { e.preventDefault(); openDetail(n.id); },
          }, n.telefoonnummer || '(geen nummer)')),
        flag
          ? el('span', { class: 'warn-badge' + (flag.amber ? ' amber' : ''), title: flag.tip }, flag.label)
          : null
      ),
      el('td', {}, persoonLink(n.verantwoordelijke_persoon_id, n.verantwoordelijke_naam)),
      el('td', {}, n.doel || el('span', { class: 'muted' }, '—')),
      el('td', {}, n.factuur_firma_id
        ? el('a', {
            class: 'person-link', href: '#', title: 'Alle details van deze firma',
            onclick: (e) => { e.preventDefault(); openFirma(n.factuur_firma_id); },
          }, n.factuur_firma_naam)
        : el('span', { class: 'muted' }, '—')),
      el('td', {}, n.leverancier_naam || el('span', { class: 'muted' }, '—')),
      el('td', {}, statusBadge(n.status))
    );
    tbody.append(tr);
  });

  const total = rows.length;
  $('#countLine').textContent =
    total === 0 ? '' : `${total} nummer${total === 1 ? '' : 's'} getoond`;
}

// ====================================================================
// Detailweergave (slide-over)
// ====================================================================
let detailRecord = null;
let detailQueue = [];  // gebruikers in belvolgorde (index 0 neemt eerst op)
const REF_KEYS = ['leverancier_id', 'factuur_firma_id', 'doorfactuur_firma_id', 'afdeling_id', 'verantwoordelijke_persoon_id'];

async function openDetail(id) {
  try {
    detailRecord = await api(`/api/numbers/${id}`);
    detailQueue = (detailRecord.gebruikers || []).map((g) => ({ persoon_id: g.persoon_id, naam: g.naam }));
    state.selectedId = id;
    renderDetail();
    $('#overlay').classList.add('open');
    $('#drawer').classList.add('open');
    $('#drawer').setAttribute('aria-hidden', 'false');
  } catch (e) {
    toast(e.message, true);
  }
}
function closeDetail() {
  $('#overlay').classList.remove('open');
  $('#drawer').classList.remove('open');
  $('#drawer').setAttribute('aria-hidden', 'true');
  state.selectedId = null;
  detailRecord = null;
}

// Invoerveld: tekst / textarea / select uit opties [{value, label}].
function detailField(label, key, opts = {}) {
  const val = detailRecord[key] ?? '';
  let input;
  if (opts.refOptions) {
    input = el('select', {},
      el('option', { value: '' }, '— geen —'),
      ...opts.refOptions.map((o) =>
        el('option', { value: o.value, ...(o.value === val ? { selected: '' } : {}) }, o.label)));
    input.value = val || '';
  } else if (opts.options) {
    input = el('select', {}, ...['', ...opts.options].map((o) =>
      el('option', { value: o, ...(o === val ? { selected: '' } : {}) }, o === '' ? '— kies —' : o)
    ));
    input.value = val;
  } else if (opts.textarea) {
    input = el('textarea', { rows: opts.rows || 2 }, val);
  } else {
    input = el('input', { type: 'text', value: val });
  }
  input.dataset.key = key;
  input.classList.add('detail-input');
  const extra = opts.after ? [opts.after] : [];
  return el('div', { class: 'field' }, el('label', {}, label), input, ...extra);
}

function refOpties(items, labelFn) {
  return items.map((x) => ({ value: x.id, label: labelFn(x) }));
}

function renderDetail() {
  const d = detailRecord;
  const drawer = $('#drawer');
  drawer.innerHTML = '';

  drawer.append(
    el('div', { class: 'drawer-head' },
      el('div', { style: 'flex:1' },
        el('div', { class: 'phone' }, d.telefoonnummer || '—'),
        el('div', { class: 'sub-line' }, [d.land, d.factuur_firma_naam, d.leverancier_naam].filter(Boolean).join(' · ') || '—')
      ),
      statusBadge(d.status),
      el('button', { class: 'icon-btn', onclick: closeDetail, title: 'Sluiten' }, '×')
    )
  );

  const body = el('div', { class: 'drawer-body' });

  if (d.is_duplicate) {
    body.append(
      el('div', { class: 'attention-banner' },
        el('div', { style: 'flex:1' },
          el('div', { html: '<b>Duplicaat nummer:</b> dit nummer komt meermaals voor in het register — controleer of dit terecht is.' })
        )
      )
    );
  }
  if ((d.aandacht || '').trim()) {
    body.append(
      el('div', { class: 'attention-banner' },
        el('div', { style: 'flex:1' },
          el('div', { html: `<b>Aandacht:</b> ${esc(d.aandacht)}` }),
          el('button', { class: 'btn btn-sm', style: 'margin-top:8px', onclick: clearAttention }, 'Markering opgelost — wissen')
        )
      )
    );
  }

  // Status omzetten
  body.append(el('div', { class: 'section-title' }, 'Status'));
  const stToggle = el('div', { class: 'status-toggle' });
  STATUSES.forEach((s) => {
    stToggle.append(
      el('button', {
        class: 'chip' + (d.status === s ? ' active' : ''),
        onclick: () => changeStatus(s),
      }, s)
    );
  });
  body.append(stToggle);
  body.append(el('div', { class: 'hint' }, 'Niet-actief verwijdert niets — het nummer blijft bewaard en vindbaar via de filter.'));

  // Kern
  body.append(el('div', { class: 'section-title' }, 'Nummer'));
  body.append(detailField('Telefoonnummer', 'telefoonnummer'));
  body.append(detailField('Doel (waarvoor dient dit nummer)', 'doel'));

  // Koppelingen — dropdowns uit de centrale lijsten
  body.append(el('div', { class: 'section-title' }, 'Koppelingen'));
  const profielLink = d.verantwoordelijke_persoon_id
    ? el('div', { class: 'hint' },
        el('a', { class: 'person-link', href: profileUrl(d.verantwoordelijke_persoon_id), target: '_blank', rel: 'noopener' },
          '→ Profiel openen in Medewerkers'))
    : null;
  body.append(detailField('Verantwoordelijke', 'verantwoordelijke_persoon_id',
    { refOptions: refOpties(state.refs.personen, (p) => p.naam), after: profielLink }));
  const grid0 = el('div', { class: 'field-grid' });
  grid0.append(detailField('Factuur-firma (wie betaalt)', 'factuur_firma_id',
    { refOptions: refOpties(state.refs.firmas, (x) => x.naam) }));
  grid0.append(detailField('Doorfactuur-firma', 'doorfactuur_firma_id',
    { refOptions: refOpties(state.refs.firmas, (x) => x.naam) }));
  grid0.append(detailField('Leverancier', 'leverancier_id',
    { refOptions: refOpties(state.refs.leveranciers.filter((l) => l.actief || l.id === d.leverancier_id), (x) => x.naam) }));
  grid0.append(detailField('Afdeling', 'afdeling_id',
    { refOptions: refOpties(state.refs.afdelingen, (x) => x.naam) }));
  body.append(grid0);

  // Gebruikers in belvolgorde (queue van de telefooncentrale).
  body.append(el('div', { class: 'section-title' }, 'Gebruikers — belvolgorde',
    el('span', { class: 'muted', style: 'font-weight:400;font-size:12px;margin-left:8px' }, '1 neemt eerst op')));
  body.append(renderQueue());

  // Details
  body.append(el('div', { class: 'section-title' }, 'Details'));
  const grid = el('div', { class: 'field-grid' });
  grid.append(detailField('Land', 'land', { options: lijstWaarden('Land') }));
  grid.append(detailField('Platform', 'platform', { options: lijstWaarden('Platform') }));
  grid.append(detailField('Type', 'type', { options: lijstWaarden('Type') }));
  body.append(grid);
  body.append(detailField('Omschrijving (waarom dit nummer bestaat)', 'omschrijving', { textarea: true, rows: 3 }));
  body.append(detailField('Aandacht (leeg = geen markering)', 'aandacht', { textarea: true }));

  // Afgeschermde inloggegevens
  body.append(
    el('div', { class: 'section-title' }, 'Inloggegevens',
      el('button', { class: 'btn btn-sm', id: 'revealBtn', onclick: toggleSecret }, 'Toon')
    )
  );
  body.append(renderSecret());

  drawer.append(body);

  drawer.append(
    el('div', { class: 'drawer-foot' },
      el('button', { class: 'btn btn-primary', onclick: saveDetail }, 'Wijzigingen opslaan'),
      el('button', { class: 'btn', onclick: closeDetail }, 'Sluiten'),
      el('button', { class: 'btn btn-danger', style: 'margin-left:auto', onclick: deleteNumber }, 'Verwijderen')
    )
  );
}

function renderQueue() {
  const wrap = el('div', { class: 'queue-box' });
  if (!detailQueue.length) {
    wrap.append(el('div', { class: 'hint' }, 'Nog geen gebruikers op dit nummer.'));
  }
  detailQueue.forEach((g, i) => {
    wrap.append(el('div', { class: 'queue-item' },
      el('span', { class: 'queue-num' }, String(i + 1)),
      el('span', { class: 'queue-naam' }, g.naam),
      el('span', { class: 'queue-btns' },
        el('button', { class: 'icon-btn', title: 'Eerder in de queue', onclick: () => moveQueue(i, -1) }, '↑'),
        el('button', { class: 'icon-btn', title: 'Later in de queue', onclick: () => moveQueue(i, 1) }, '↓'),
        el('button', { class: 'icon-btn', title: 'Uit de queue halen', onclick: () => { detailQueue.splice(i, 1); refreshQueue(); } }, '×')
      )));
  });
  const beschikbaar = state.refs.personen.filter((p) => !detailQueue.some((g) => g.persoon_id === p.id));
  if (beschikbaar.length) {
    const sel = el('select', { class: 'queue-add' },
      el('option', { value: '' }, '+ gebruiker toevoegen'),
      ...beschikbaar.map((p) => el('option', { value: p.id }, p.naam)));
    sel.addEventListener('change', () => {
      const p = state.refs.personen.find((x) => x.id === sel.value);
      if (p) { detailQueue.push({ persoon_id: p.id, naam: p.naam }); refreshQueue(); }
    });
    wrap.append(sel);
  }
  return wrap;
}
function moveQueue(i, d) {
  const j = i + d;
  if (j < 0 || j >= detailQueue.length) return;
  [detailQueue[i], detailQueue[j]] = [detailQueue[j], detailQueue[i]];
  refreshQueue();
}
function refreshQueue() {
  const oud = document.querySelector('.queue-box');
  if (oud) oud.replaceWith(renderQueue());
}

let secretRevealed = false;
function renderSecret() {
  const s = detailRecord.geheim || { kaartnummer: '', pin1: '', puk1: '', pin2: '', puk2: '', notitie: '' };
  const box = el('div', { class: 'secret-box' });
  if (!secretRevealed) {
    box.append(
      el('div', { class: 'secret-locked' },
        el('div', {}, 'PIN, PUK en kaartnummer zijn verborgen.'),
        el('div', { class: 'hint' }, 'Klik op “Toon” bovenaan deze sectie om ze te bekijken of te bewerken.')
      )
    );
    return box;
  }
  const grid = el('div', { class: 'field-grid' });
  const f = (label, key) => {
    const input = el('input', { type: 'text', value: s[key] || '', class: 'secret-input mono' });
    input.dataset.skey = key;
    return el('div', { class: 'field' }, el('label', {}, label), input);
  };
  grid.append(f('Kaartnummer (SSN)', 'kaartnummer'));
  grid.append(f('Notitie', 'notitie'));
  grid.append(f('PIN 1', 'pin1'));
  grid.append(f('PUK 1', 'puk1'));
  grid.append(f('PIN 2', 'pin2'));
  grid.append(f('PUK 2', 'puk2'));
  box.append(grid);
  box.append(el('button', { class: 'btn btn-sm', onclick: saveSecret }, 'Inloggegevens opslaan'));
  return box;
}
function toggleSecret() {
  secretRevealed = !secretRevealed;
  const btn = $('#revealBtn');
  if (btn) btn.textContent = secretRevealed ? 'Verberg' : 'Toon';
  const old = $('.secret-box');
  if (old) old.replaceWith(renderSecret());
}

async function saveDetail() {
  const payload = {};
  document.querySelectorAll('.detail-input').forEach((inp) => {
    payload[inp.dataset.key] = REF_KEYS.includes(inp.dataset.key)
      ? (inp.value || null)
      : inp.value;
  });
  payload.gebruiker_ids = detailQueue.map((g) => g.persoon_id);
  try {
    await api(`/api/numbers/${detailRecord.id}`, { method: 'PUT', body: payload });
    toast('Opgeslagen.');
    detailRecord = await api(`/api/numbers/${detailRecord.id}`);
    renderDetail();
    load();
  } catch (e) {
    toast(e.message, true);
  }
}
async function saveSecret() {
  const payload = {};
  document.querySelectorAll('.secret-input').forEach((inp) => {
    payload[inp.dataset.skey] = inp.value;
  });
  try {
    const geheim = await api(`/api/numbers/${detailRecord.id}/secret`, { method: 'PUT', body: payload });
    detailRecord.geheim = geheim;
    toast('Inloggegevens opgeslagen.');
  } catch (e) {
    toast(e.message, true);
  }
}
async function changeStatus(s) {
  try {
    await api(`/api/numbers/${detailRecord.id}/status`, { method: 'PATCH', body: { status: s } });
    detailRecord.status = s;
    renderDetail();
    load();
    toast(`Status: ${s}`);
  } catch (e) {
    toast(e.message, true);
  }
}
async function clearAttention() {
  try {
    await api(`/api/numbers/${detailRecord.id}/clear-attention`, { method: 'POST' });
    detailRecord.aandacht = '';
    renderDetail();
    load();
    toast('Markering gewist.');
  } catch (e) {
    toast(e.message, true);
  }
}
async function deleteNumber() {
  const ok = confirm(
    `Dit nummer DEFINITIEF verwijderen?\n\n${detailRecord.telefoonnummer} — ${detailRecord.doel || ''}\n\n` +
    'Tip: om historiek te bewaren kun je beter de status op "Niet-actief" zetten. Verwijderen kan niet ongedaan gemaakt worden.'
  );
  if (!ok) return;
  try {
    await api(`/api/numbers/${detailRecord.id}`, { method: 'DELETE' });
    toast('Nummer verwijderd.');
    closeDetail();
    load();
  } catch (e) {
    toast(e.message, true);
  }
}

// ====================================================================
// Firma-detail (alles wat aan een firma hangt, duidelijk benoemd)
// ====================================================================
async function openFirma(id) {
  try {
    const d = await api(`/api/firmas/${id}`);
    renderFirmaDetail(d);
    $('#overlay').classList.add('open');
    $('#drawer').classList.add('open');
    $('#drawer').setAttribute('aria-hidden', 'false');
  } catch (e) {
    toast(e.message, true);
  }
}

function firmaSectie(body, titel, items, renderItem) {
  body.append(el('div', { class: 'section-title' }, titel,
    el('span', { class: 'muted', style: 'font-weight:400;letter-spacing:0;text-transform:none' },
      String(items.length))));
  if (!items.length) {
    body.append(el('div', { class: 'hint' }, 'Geen.'));
    return;
  }
  const box = el('div', { class: 'queue-box' });
  items.forEach((it) => box.append(renderItem(it)));
  body.append(box);
}

function renderFirmaDetail(d) {
  const drawer = $('#drawer');
  drawer.innerHTML = '';

  drawer.append(
    el('div', { class: 'drawer-head' },
      el('div', { style: 'flex:1' },
        el('div', { class: 'phone' }, d.firma.naam),
        el('div', { class: 'sub-line' }, [d.firma.code, d.firma.land].filter(Boolean).join(' · '))
      ),
      statusBadge(d.firma.actief ? 'Actief' : 'Niet-actief'),
      el('button', { class: 'icon-btn', onclick: closeDetail, title: 'Sluiten' }, '×')
    )
  );

  const body = el('div', { class: 'drawer-body' });

  const nummerRij = (n) => el('div', { class: 'queue-item' },
    el('a', {
      class: 'person-link', href: '#',
      onclick: (e) => { e.preventDefault(); openDetail(n.id); },
    }, n.telefoonnummer || '(geen nummer)'),
    el('span', { class: 'muted', style: 'flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap' }, n.doel || ''),
    statusBadge(n.status));

  firmaSectie(body, 'Telefoonnummers — gefactureerd aan deze firma', d.nummers_factuur, nummerRij);
  firmaSectie(body, 'Telefoonnummers — doorgefactureerd aan deze firma', d.nummers_doorfactuur, nummerRij);
  firmaSectie(body, 'E-mailadressen van deze firma', d.emails, (m) =>
    el('div', { class: 'queue-item' },
      el('span', { class: 'mono' }, m.adres),
      el('span', { class: 'muted', style: 'flex:1' },
        m.verantwoordelijke_naam ? 'verantwoordelijke: ' + m.verantwoordelijke_naam : ''),
      m.verantwoordelijke_naam ? null : el('span', { class: 'open-badge' }, 'OPEN')));
  firmaSectie(body, 'Medewerkers — in dienst bij deze firma', d.in_dienst, (p) =>
    el('div', { class: 'queue-item' }, persoonLink(p.id, p.naam)));
  firmaSectie(body, 'Medewerkers — verrichten diensten voor deze firma', d.diensten, (p) =>
    el('div', { class: 'queue-item' }, persoonLink(p.id, p.naam)));

  body.append(el('div', { class: 'hint', style: 'margin-top:14px' },
    'Firma-gegevens (naam, code, land) beheer je centraal; wat hier hangt volgt de koppelingen op nummers, adressen en personen.'));

  drawer.append(body);
  drawer.append(
    el('div', { class: 'drawer-foot' },
      el('button', { class: 'btn', onclick: closeDetail }, 'Sluiten')
    )
  );
}

// ====================================================================
// Nummer toevoegen
// ====================================================================
let dupTimer;
function addField(label, key, opts = {}) {
  let input;
  if (opts.refOptions) {
    input = el('select', {},
      el('option', { value: '' }, '— geen —'),
      ...opts.refOptions.map((o) => el('option', { value: o.value }, o.label)));
  } else if (opts.options) {
    input = el('select', {}, ...['', ...opts.options].map((o) =>
      el('option', { value: o }, o === '' ? '— kies —' : o)
    ));
  } else if (opts.textarea) {
    input = el('textarea', { rows: 2 });
  } else {
    input = el('input', { type: 'text', placeholder: opts.placeholder || '' });
  }
  input.dataset.akey = key;
  input.classList.add('add-input');
  return el('div', { class: 'field' }, el('label', {}, label + (opts.req ? ' *' : '')), input,
    opts.hint ? el('div', { class: 'hint' }, opts.hint) : null);
}

function openAdd() {
  const body = $('#addBody');
  body.innerHTML = '';
  $('#addError').textContent = '';

  const dupBox = el('div', { id: 'dupBox' });
  body.append(dupBox);

  body.append(addField('Telefoonnummer', 'telefoonnummer', { req: true, placeholder: 'bv. 016 79 21 61' }));
  body.append(addField('Doel', 'doel', { req: true, placeholder: 'bv. algemeen nummer sales' }));

  const grid1 = el('div', { class: 'field-grid' });
  grid1.append(addField('Status', 'status', { options: STATUSES, req: true }));
  grid1.append(addField('Land', 'land', { options: lijstWaarden('Land'), hint: 'Wordt automatisch afgeleid uit het nummer.' }));
  body.append(grid1);

  body.append(addField('Verantwoordelijke', 'verantwoordelijke_persoon_id',
    { refOptions: refOpties(state.refs.personen, (p) => p.naam) }));
  const grid2 = el('div', { class: 'field-grid' });
  grid2.append(addField('Factuur-firma', 'factuur_firma_id',
    { refOptions: refOpties(state.refs.firmas, (x) => x.naam) }));
  grid2.append(addField('Doorfactuur-firma', 'doorfactuur_firma_id',
    { refOptions: refOpties(state.refs.firmas, (x) => x.naam) }));
  grid2.append(addField('Leverancier', 'leverancier_id',
    { refOptions: refOpties(state.refs.leveranciers.filter((l) => l.actief), (x) => x.naam) }));
  grid2.append(addField('Afdeling', 'afdeling_id',
    { refOptions: refOpties(state.refs.afdelingen, (x) => x.naam) }));
  body.append(grid2);

  const grid3 = el('div', { class: 'field-grid' });
  grid3.append(addField('Platform', 'platform', { options: lijstWaarden('Platform') }));
  grid3.append(addField('Type', 'type', { options: lijstWaarden('Type') }));
  body.append(grid3);
  body.append(addField('Omschrijving', 'omschrijving', { textarea: true }));

  const statusSel = body.querySelector('[data-akey="status"]');
  if (statusSel) statusSel.value = 'Actief';

  const phoneInput = body.querySelector('[data-akey="telefoonnummer"]');
  phoneInput.addEventListener('input', () => {
    clearTimeout(dupTimer);
    dupTimer = setTimeout(() => checkDuplicate(phoneInput.value), 300);
  });

  $('#addModal').classList.add('open');
  phoneInput.focus();
}
function closeAdd() {
  $('#addModal').classList.remove('open');
}

async function checkDuplicate(phone) {
  const dupBox = $('#dupBox');
  if (!dupBox) return;
  if (!phone.trim()) { dupBox.innerHTML = ''; return; }
  try {
    const r = await api(`/api/numbers/check?phone=${encodeURIComponent(phone)}`);
    const countrySel = document.querySelector('[data-akey="land"]');
    if (countrySel && !countrySel.value && r.country) countrySel.value = r.country;

    if (r.duplicate && r.matches.length) {
      const m = r.matches[0];
      dupBox.innerHTML =
        `<div class="dup-warning"><b>Dit nummer bestaat al</b> — ${esc(m.telefoonnummer)} ` +
        `(${esc(m.doel || '')}, status ${esc(m.status)}). ` +
        `Toevoegen wordt geblokkeerd om dubbele abonnementen te vermijden.</div>`;
    } else {
      dupBox.innerHTML = '';
    }
  } catch (_) { /* stil */ }
}

async function saveAdd() {
  const payload = {};
  document.querySelectorAll('.add-input').forEach((inp) => {
    payload[inp.dataset.akey] = REF_KEYS.includes(inp.dataset.akey)
      ? (inp.value || null)
      : inp.value;
  });
  const errEl = $('#addError');
  errEl.textContent = '';
  if (!payload.telefoonnummer || !payload.telefoonnummer.trim()) { errEl.textContent = 'Telefoonnummer is verplicht.'; return; }
  if (!payload.doel || !payload.doel.trim()) { errEl.textContent = '“Doel” is verplicht.'; return; }
  if (!payload.status) payload.status = 'Actief';
  try {
    const created = await api('/api/numbers', { method: 'POST', body: payload });
    closeAdd();
    toast('Nummer toegevoegd.');
    await load();
    openDetail(created.id);
  } catch (e) {
    if (e.status === 409 && e.data && e.data.existing) {
      const x = e.data.existing;
      errEl.innerHTML = '';
      $('#dupBox').innerHTML =
        `<div class="dup-warning"><b>Geblokkeerd: nummer bestaat al</b> — ${esc(x.telefoonnummer)} ` +
        `(${esc(x.doel || '')}${x.status ? ', status ' + esc(x.status) : ''}).</div>`;
    } else {
      errEl.textContent = e.message;
    }
  }
}

// ====================================================================
// Lijstenbeheer (app-eigen keuzewaarden + leveranciers)
// ====================================================================
const LIST_LABELS = { Land: 'Landen', Platform: 'Platformen', Type: 'Types' };
const LEV_TAB = '__leveranciers__';
let activeListCat = 'Land';

function openLists() {
  const cats = Object.keys(state.refs.lijsten);
  if (activeListCat !== LEV_TAB && !cats.includes(activeListCat)) activeListCat = cats[0] || LEV_TAB;
  renderListsModal();
  $('#listsModal').classList.add('open');
}
function closeLists() { $('#listsModal').classList.remove('open'); }

function renderListsModal() {
  const body = $('#listsBody');
  body.innerHTML = '';
  const cats = Object.keys(state.refs.lijsten);

  const catBar = el('div', { class: 'lists-cats' });
  [...cats, LEV_TAB].forEach((c) => {
    catBar.append(
      el('button', {
        class: 'chip' + (c === activeListCat ? ' active' : ''),
        onclick: () => { activeListCat = c; renderListsModal(); },
      }, c === LEV_TAB ? 'Leveranciers' : (LIST_LABELS[c] || c))
    );
  });
  body.append(catBar);

  if (activeListCat === LEV_TAB) {
    renderLeveranciersBeheer(body);
    return;
  }

  const values = state.refs.lijsten[activeListCat] || [];
  const list = el('div', { class: 'list-values' });
  values.forEach((v) => {
    const input = el('input', { type: 'text', value: v.waarde });
    const save = async () => {
      if (input.value.trim() === v.waarde || !input.value.trim()) { input.value = v.waarde; return; }
      try {
        await api(`/api/lists/${v.id}`, { method: 'PUT', body: { value: input.value.trim() } });
        toast('Lijst bijgewerkt.');
      } catch (e) { toast(e.message, true); input.value = v.waarde; }
    };
    input.addEventListener('blur', save);
    input.addEventListener('keydown', (e) => { if (e.key === 'Enter') input.blur(); });
    list.append(
      el('div', { class: 'list-value-row' },
        input,
        el('button', {
          class: 'icon-btn', title: 'Verwijderen',
          onclick: async () => {
            if (!confirm(`Waarde “${v.waarde}” verwijderen uit ${LIST_LABELS[activeListCat] || activeListCat}?`)) return;
            try { await api(`/api/lists/${v.id}`, { method: 'DELETE' }); toast('Verwijderd.'); }
            catch (e) { toast(e.message, true); }
          },
        }, '×')
      )
    );
  });
  body.append(list);

  const newInput = el('input', { type: 'text', placeholder: 'Nieuwe waarde toevoegen…' });
  const addVal = async () => {
    const value = newInput.value.trim();
    if (!value) return;
    try {
      await api('/api/lists', { method: 'POST', body: { category: activeListCat, value } });
      newInput.value = '';
      toast('Toegevoegd.');
    } catch (e) { toast(e.message, true); }
  };
  newInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') addVal(); });
  body.append(
    el('div', { class: 'add-value-row' },
      newInput,
      el('button', { class: 'btn btn-primary', onclick: addVal }, 'Toevoegen')
    )
  );
}

// Leveranciers: centrale lijst (kern) — hernoemen + aan/uit, geen verwijderen.
function renderLeveranciersBeheer(body) {
  body.append(el('div', { class: 'hint', style: 'margin-bottom:8px' },
    'Leveranciers zijn een centrale lijst. Uitzetten i.p.v. verwijderen — verwijzingen blijven zo geldig.'));
  const list = el('div', { class: 'list-values' });
  state.refs.leveranciers.forEach((l) => {
    const input = el('input', { type: 'text', value: l.naam });
    const save = async () => {
      if (input.value.trim() === l.naam || !input.value.trim()) { input.value = l.naam; return; }
      try {
        await api(`/api/leveranciers/${l.id}`, { method: 'PUT', body: { naam: input.value.trim() } });
        toast('Leverancier hernoemd.');
        await refreshRefs(); renderListsModal();
      } catch (e) { toast(e.message, true); input.value = l.naam; }
    };
    input.addEventListener('blur', save);
    input.addEventListener('keydown', (e) => { if (e.key === 'Enter') input.blur(); });
    list.append(
      el('div', { class: 'list-value-row' },
        input,
        el('button', {
          class: 'btn btn-sm', title: l.actief ? 'Uitzetten' : 'Aanzetten',
          onclick: async () => {
            try {
              await api(`/api/leveranciers/${l.id}`, { method: 'PUT', body: { actief: !l.actief } });
              toast(l.actief ? 'Uitgezet.' : 'Aangezet.');
              await refreshRefs(); renderListsModal();
            } catch (e) { toast(e.message, true); }
          },
        }, l.actief ? 'Actief' : 'Uit')
      )
    );
  });
  body.append(list);

  const newInput = el('input', { type: 'text', placeholder: 'Nieuwe leverancier toevoegen…' });
  const addVal = async () => {
    const naam = newInput.value.trim();
    if (!naam) return;
    try {
      await api('/api/leveranciers', { method: 'POST', body: { naam } });
      newInput.value = '';
      toast('Toegevoegd.');
      await refreshRefs(); renderListsModal();
    } catch (e) { toast(e.message, true); }
  };
  newInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') addVal(); });
  body.append(
    el('div', { class: 'add-value-row' },
      newInput,
      el('button', { class: 'btn btn-primary', onclick: addVal }, 'Toevoegen')
    )
  );
}

// ====================================================================
// E-mailadressen (tab 2)
// ====================================================================
function renderEmailFilters() {
  const f = state.emailFilters;
  chipRow($('#emailOpenChips'),
    [{ value: '', label: 'Alles' }, { value: '1', label: 'Open eindjes' }],
    f.open ? '1' : '', (v) => { f.open = v === '1'; loadEmails(); renderEmailFilters(); });
}

function renderEmails() {
  const tbody = $('#emailRows');
  tbody.innerHTML = '';
  const rows = state.emails;
  $('#emailEmptyState').style.display = rows.length ? 'none' : 'block';

  rows.forEach((m) => {
    const tr = el('tr', { onclick: () => openEmailModal(m) });
    tr.append(
      el('td', { class: 'mono' }, m.adres),
      el('td', {}, m.firma_id
        ? el('a', {
            class: 'person-link', href: '#', title: 'Alle details van deze firma',
            onclick: (e) => { e.preventDefault(); e.stopPropagation(); openFirma(m.firma_id); },
          }, m.firma_naam)
        : el('span', { class: 'muted' }, '—')),
      el('td', {}, m.verantwoordelijke_persoon_id
        ? persoonLink(m.verantwoordelijke_persoon_id, m.verantwoordelijke_naam)
        : el('span', { class: 'open-badge', title: 'Geen verantwoordelijke — open eindje' }, 'OPEN')),
      el('td', { title: (m.gebruikers || []).map((g) => g.naam).join(', ') },
        (m.gebruikers || []).length
          ? (m.gebruikers || []).map((g) => g.naam).join(', ')
          : el('span', { class: 'muted' }, '—')),
      el('td', {}, m.omschrijving || el('span', { class: 'muted' }, '—')),
      el('td', {}, statusBadge(m.actief ? 'Actief' : 'Niet-actief'))
    );
    tbody.append(tr);
  });

  const total = rows.length;
  $('#emailCountLine').textContent =
    total === 0 ? '' : `${total} adres${total === 1 ? '' : 'sen'} getoond`;
}

let emailRecord = null;
let emailGebruikers = [];  // wie op de mailbox ingelogd zijn (multi)

function renderEmailGebruikers() {
  const wrap = el('div', { class: 'queue-box', id: 'emailGebruikersBox' });
  if (!emailGebruikers.length) {
    wrap.append(el('div', { class: 'hint' }, 'Nog geen gebruikers op dit adres.'));
  }
  emailGebruikers.forEach((g, i) => {
    wrap.append(el('div', { class: 'queue-item' },
      el('span', { class: 'queue-naam' }, g.naam),
      el('span', { class: 'queue-btns' },
        el('button', { class: 'icon-btn', title: 'Verwijderen', onclick: () => {
          emailGebruikers.splice(i, 1); refreshEmailGebruikers();
        } }, '×')
      )));
  });
  const beschikbaar = state.refs.personen.filter((p) => !emailGebruikers.some((g) => g.persoon_id === p.id));
  if (beschikbaar.length) {
    const sel = el('select', { class: 'queue-add' },
      el('option', { value: '' }, '+ gebruiker toevoegen'),
      ...beschikbaar.map((p) => el('option', { value: p.id }, p.naam)));
    sel.addEventListener('change', () => {
      const p = state.refs.personen.find((x) => x.id === sel.value);
      if (p) { emailGebruikers.push({ persoon_id: p.id, naam: p.naam }); refreshEmailGebruikers(); }
    });
    wrap.append(sel);
  }
  return wrap;
}
function refreshEmailGebruikers() {
  const oud = document.getElementById('emailGebruikersBox');
  if (oud) oud.replaceWith(renderEmailGebruikers());
}
function openEmailModal(record) {
  emailRecord = record || null;
  emailGebruikers = (record && record.gebruikers ? record.gebruikers : [])
    .map((g) => ({ persoon_id: g.persoon_id, naam: g.naam }));
  const body = $('#emailBody');
  body.innerHTML = '';
  $('#emailError').textContent = '';
  $('#emailModalTitle').textContent = record ? 'Adres bewerken' : 'Adres toevoegen';
  $('#emailDelete').style.display = record ? '' : 'none';

  const f = (label, key, opts = {}) => {
    const val = record ? (record[key] ?? '') : '';
    let input;
    if (opts.refOptions) {
      input = el('select', {},
        el('option', { value: '' }, '— geen —'),
        ...opts.refOptions.map((o) =>
          el('option', { value: o.value, ...(o.value === val ? { selected: '' } : {}) }, o.label)));
      input.value = val || '';
    } else if (opts.checkbox) {
      input = el('input', { type: 'checkbox', ...((record ? record[key] : true) ? { checked: '' } : {}) });
    } else if (opts.textarea) {
      input = el('textarea', { rows: 2 }, val);
    } else {
      input = el('input', { type: 'text', value: val, placeholder: opts.placeholder || '' });
    }
    input.dataset.ekey = key;
    input.classList.add('email-input');
    return el('div', { class: 'field' }, el('label', {}, label + (opts.req ? ' *' : '')), input);
  };

  body.append(f('E-mailadres', 'adres', { req: true, placeholder: 'bv. info@unabo.be' }));
  const grid = el('div', { class: 'field-grid' });
  grid.append(f('Firma', 'firma_id', { refOptions: refOpties(state.refs.firmas, (x) => x.naam) }));
  grid.append(f('Verantwoordelijke', 'verantwoordelijke_persoon_id', { refOptions: refOpties(state.refs.personen, (p) => p.naam) }));
  body.append(grid);
  body.append(el('div', { class: 'field' },
    el('label', {}, 'Gebruikers (ingelogd op dit adres)'),
    renderEmailGebruikers()));
  body.append(f('Omschrijving', 'omschrijving', { textarea: true }));
  body.append(f('Actief', 'actief', { checkbox: true }));

  $('#emailModal').classList.add('open');
}
function closeEmailModal() {
  $('#emailModal').classList.remove('open');
  emailRecord = null;
}

async function saveEmail() {
  const payload = {};
  document.querySelectorAll('.email-input').forEach((inp) => {
    if (inp.type === 'checkbox') payload[inp.dataset.ekey] = inp.checked;
    else if (['firma_id', 'verantwoordelijke_persoon_id'].includes(inp.dataset.ekey)) payload[inp.dataset.ekey] = inp.value || null;
    else payload[inp.dataset.ekey] = inp.value;
  });
  payload.gebruiker_ids = emailGebruikers.map((g) => g.persoon_id);
  const errEl = $('#emailError');
  errEl.textContent = '';
  if (!payload.adres || !payload.adres.includes('@')) { errEl.textContent = 'Een geldig e-mailadres is verplicht.'; return; }
  try {
    if (emailRecord) {
      await api(`/api/emails/${emailRecord.id}`, { method: 'PUT', body: payload });
      toast('Adres bijgewerkt.');
    } else {
      await api('/api/emails', { method: 'POST', body: payload });
      toast('Adres toegevoegd.');
    }
    closeEmailModal();
    loadEmails();
  } catch (e) {
    errEl.textContent = e.message;
  }
}

async function deleteEmail() {
  if (!emailRecord) return;
  if (!confirm(`E-mailadres “${emailRecord.adres}” definitief verwijderen?`)) return;
  try {
    await api(`/api/emails/${emailRecord.id}`, { method: 'DELETE' });
    toast('Adres verwijderd.');
    closeEmailModal();
    loadEmails();
  } catch (e) {
    toast(e.message, true);
  }
}

async function loadEmails() {
  const p = new URLSearchParams();
  if (state.emailFilters.q) p.set('q', state.emailFilters.q);
  if (state.emailFilters.open) p.set('open', '1');
  state.emails = await api('/api/emails?' + p.toString());
  renderEmails();
}

// ====================================================================
// Data laden
// ====================================================================
async function refreshRefs() {
  state.refs = await api('/api/refs');
}

async function load() {
  const f = state.filters;
  const p = new URLSearchParams();
  if (f.land) p.set('land', f.land);
  if (f.status) p.set('status', f.status);
  if (f.firma.length) p.set('firma', f.firma.join(','));
  if (f.leverancier) p.set('leverancier', f.leverancier);
  if (f.q) p.set('q', f.q);
  if (f.duplicates) p.set('duplicates', '1');
  if (f.attention) p.set('attention', '1');
  const [numbers, stats] = await Promise.all([
    api('/api/numbers?' + p.toString()),
    api('/api/stats'),
  ]);
  state.numbers = numbers;
  state.stats = stats;
  renderKpis();
  renderTable();
}

async function refreshAll() {
  await refreshRefs();
  renderFilters();
  renderEmailFilters();
  await load();
  if ($('#listsModal').classList.contains('open')) renderListsModal();
}

// ---- Live sync (SSE) ----------------------------------------------
function connectEvents() {
  try {
    const es = new EventSource('/api/events');
    let debounce;
    es.onmessage = (ev) => {
      let msg = {};
      try { msg = JSON.parse(ev.data); } catch (_) { return; }
      if (msg.type === 'hello') return;
      clearTimeout(debounce);
      debounce = setTimeout(async () => {
        if (msg.type === 'lists' || msg.type === 'refs') {
          await refreshRefs();
          renderFilters();
          if ($('#listsModal').classList.contains('open')) renderListsModal();
        }
        if (msg.type === 'emails') {
          await loadEmails();
        }
        await load();
        if (state.selectedId && detailRecord && msg.id === state.selectedId) {
          try { detailRecord = await api(`/api/numbers/${state.selectedId}`); renderDetail(); } catch (_) {}
        }
      }, 150);
    };
    es.onerror = () => { /* EventSource probeert vanzelf opnieuw */ };
  } catch (_) { /* geen SSE — app werkt nog steeds, zonder live sync */ }
}

// ====================================================================
// Init + events
// ====================================================================
function setTab(name) {
  const valid = ['telefonie', 'email'];
  if (!valid.includes(name)) name = 'telefonie';
  document.querySelectorAll('.tab').forEach((t) => t.classList.toggle('active', t.dataset.tab === name));
  document.querySelectorAll('.view').forEach((v) => { v.hidden = v.id !== 'view-' + name; });
  if (name === 'email') loadEmails().catch(() => {});
  if (location.hash.slice(1) !== name) {
    history.replaceState(null, '', name === 'telefonie' ? location.pathname : '#' + name);
  }
}

function bind() {
  document.querySelectorAll('.tab').forEach((t) =>
    t.addEventListener('click', () => setTab(t.dataset.tab))
  );
  setTab(location.hash.slice(1) || 'telefonie');

  $('#btnAdd').addEventListener('click', openAdd);
  $('#btnLists').addEventListener('click', openLists);
  $('#btnExport').addEventListener('click', () => { window.location.href = '/api/export'; });
  $('#overlay').addEventListener('click', closeDetail);
  $('#addSave').addEventListener('click', saveAdd);
  $('#btnAddEmail').addEventListener('click', () => openEmailModal(null));
  $('#emailSave').addEventListener('click', saveEmail);
  $('#emailDelete').addEventListener('click', deleteEmail);
  document.querySelectorAll('[data-close-add]').forEach((b) => b.addEventListener('click', closeAdd));
  document.querySelectorAll('[data-close-lists]').forEach((b) => b.addEventListener('click', closeLists));
  document.querySelectorAll('[data-close-email]').forEach((b) => b.addEventListener('click', closeEmailModal));

  const search = $('#search');
  let st;
  search.addEventListener('input', () => {
    clearTimeout(st);
    st = setTimeout(() => { state.filters.q = search.value.trim(); load(); }, 250);
  });
  const emailSearch = $('#emailSearch');
  let est;
  emailSearch.addEventListener('input', () => {
    clearTimeout(est);
    est = setTimeout(() => { state.emailFilters.q = emailSearch.value.trim(); loadEmails(); }, 250);
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      if ($('#addModal').classList.contains('open')) closeAdd();
      else if ($('#emailModal').classList.contains('open')) closeEmailModal();
      else if ($('#listsModal').classList.contains('open')) closeLists();
      else if ($('#drawer').classList.contains('open')) closeDetail();
    }
  });
}

// Alleen-lezen modus: verberg de bewerkknoppen en toon een label. De server
// dwingt het echt af (403); dit is enkel de UI die zich ernaar schikt.
function applyEditMode(isEditor) {
  document.body.classList.toggle('readonly', !isEditor);
  ['#btnAdd', '#btnLists', '#btnAddEmail'].forEach((sel) => {
    const node = $(sel);
    if (node) node.style.display = isEditor ? '' : 'none';
  });
  if (!isEditor) {
    const chip = $('#userName');
    if (chip && !chip.dataset.ro) {
      chip.dataset.ro = '1';
      chip.textContent += ' · alleen-lezen';
    }
  }
}

async function init() {
  // Hash vastleggen VOOR bind(): setTab() normaliseert de URL en zou de
  // deep-link (#nummer=<uuid>) anders wissen voordat we hem gelezen hebben.
  const startHash = location.hash;
  bind();
  try {
    const me = await api('/api/me');
    $('#userName').textContent = me.username;
    applyEditMode(me.isEditor);
  } catch (_) { $('#userName').textContent = 'onbekend'; }
  await refreshAll();
  // Deep-link vanuit het medewerkersprofiel: open het nummerdetail.
  const dl = startHash.match(/^#nummer=([0-9a-f-]{36})$/i);
  if (dl) openDetail(dl[1]);
  connectEvents();
}

init();
