// Series & Races landing page.
// Fetches every regatta and every race in one shot, groups races by
// regatta, and renders a card grid + a tail section for standalone
// races. Click anywhere on a card → race.html?regatta=<id>; click a
// standalone-race row → race.html?race=<id>.

const API_BASE = window.SAILFRAMES_API_URL || window.location.origin;

function esc(s) {
    if (s == null) return '';
    return String(s)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function fmtDateRange(startDate, endDate) {
    if (!startDate) return '';
    const fmt = (d) => new Date(d + 'T12:00:00').toLocaleDateString('en-US',
        { month: 'short', day: 'numeric', year: 'numeric' });
    if (!endDate || endDate === startDate) return fmt(startDate);
    // Same year? Drop year on the start side for visual brevity.
    if (startDate.slice(0, 4) === endDate.slice(0, 4)) {
        const fmtNoYear = (d) => new Date(d + 'T12:00:00').toLocaleDateString('en-US',
            { month: 'short', day: 'numeric' });
        return `${fmtNoYear(startDate)} – ${fmt(endDate)}`;
    }
    return `${fmt(startDate)} – ${fmt(endDate)}`;
}

function fmtShortDate(date) {
    if (!date) return '';
    return new Date(date + 'T12:00:00').toLocaleDateString('en-US',
        { month: 'short', day: 'numeric', year: 'numeric' });
}

// Pull the human label off a regatta's boat_class which can be a
// legacy string ("J/80") or the structured {id,name,loa_m,...} object
// introduced when the race-edit form moved to the dropdown.
function boatClassLabel(bc) {
    if (!bc) return '';
    if (typeof bc === 'string') return bc.trim();
    if (typeof bc === 'object' && bc.name) return String(bc.name).trim();
    return '';
}

let _allRegattas = [];
let _racesByRegatta = new Map();   // regatta_id → races[] sorted asc by date
let _orphanRaces = [];

async function init() {
    const grid = document.getElementById('rl-regattas-grid');
    const orphanSection = document.getElementById('rl-orphan-section');
    const orphanList = document.getElementById('rl-orphan-list');

    try {
        const [regResp, racesResp] = await Promise.all([
            fetch(`${API_BASE}/api/regattas`),
            fetch(`${API_BASE}/api/races`),
        ]);
        if (!regResp.ok) throw new Error(`regattas HTTP ${regResp.status}`);
        if (!racesResp.ok) throw new Error(`races HTTP ${racesResp.status}`);
        const regData = await regResp.json();
        const raceData = await racesResp.json();
        _allRegattas = regData.regattas || [];
        const allRaces = raceData.races || [];

        _racesByRegatta = new Map();
        _orphanRaces = [];
        for (const r of allRaces) {
            if (r.regatta_id) {
                if (!_racesByRegatta.has(r.regatta_id)) _racesByRegatta.set(r.regatta_id, []);
                _racesByRegatta.get(r.regatta_id).push(r);
            } else {
                _orphanRaces.push(r);
            }
        }
        for (const arr of _racesByRegatta.values()) {
            arr.sort((a, b) => (a.start_time || '').localeCompare(b.start_time || ''));
        }
        _orphanRaces.sort((a, b) => (b.start_time || '').localeCompare(a.start_time || ''));
    } catch (err) {
        console.error('[Races] load failed:', err);
        grid.innerHTML = `<div class="rl-empty">Couldn't load series. <code>${esc(err.message)}</code></div>`;
        return;
    }

    render();
    wireToolbar();
    if (_orphanRaces.length) {
        orphanSection.hidden = false;
        renderOrphans(orphanList);
    }
}

function render() {
    const grid = document.getElementById('rl-regattas-grid');
    const sortMode = document.getElementById('rl-sort')?.value || 'newest';
    const search = (document.getElementById('rl-search')?.value || '').trim().toLowerCase();

    let regattas = _allRegattas.slice();

    if (search) {
        regattas = regattas.filter(r => {
            const haystack = [
                r.name, r.venue, boatClassLabel(r.boat_class),
            ].filter(Boolean).join(' ').toLowerCase();
            return haystack.includes(search);
        });
    }

    regattas.sort((a, b) => {
        if (sortMode === 'name') {
            return (a.name || '').localeCompare(b.name || '');
        }
        // Date-based sorts: prefer start_date, fall back to most-recent
        // race date — covers regattas that haven't filled in start_date.
        const aRaces = _racesByRegatta.get(a.regatta_id) || [];
        const bRaces = _racesByRegatta.get(b.regatta_id) || [];
        const aMost = aRaces.length ? aRaces[aRaces.length - 1].date : a.start_date;
        const bMost = bRaces.length ? bRaces[bRaces.length - 1].date : b.start_date;
        const cmp = (bMost || '').localeCompare(aMost || '');
        return sortMode === 'oldest' ? -cmp : cmp;
    });

    if (!regattas.length) {
        grid.innerHTML = `<div class="rl-empty">
            No series yet. <a href="./events.html">Create one →</a>
        </div>`;
        return;
    }

    grid.innerHTML = regattas.map(renderCard).join('');

    // Click anywhere on a card → navigate to the dashboard. Card is a
    // <div role="link"> rather than an <a> so the inner doc <a>s are
    // valid HTML; we re-implement link semantics here. Clicks that
    // landed inside an <a> (the doc chips) are ignored — the anchor
    // handles its own navigation in a new tab.
    grid.querySelectorAll('.rl-card[data-href]').forEach(card => {
        card.addEventListener('click', (e) => {
            if (e.target.closest('a')) return;
            const href = card.getAttribute('data-href');
            if (href) location.href = href;
        });
        // Keyboard parity for accessibility: Enter/Space opens the card.
        card.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                if (e.target.closest('a')) return;
                e.preventDefault();
                const href = card.getAttribute('data-href');
                if (href) location.href = href;
            }
        });
    });
}

function renderCard(r) {
    const races = _racesByRegatta.get(r.regatta_id) || [];
    const raceCount = races.length;
    const className = boatClassLabel(r.boat_class);

    // Docs row: only the URL fields that are actually set become chips.
    // Built bottom-up here so any future field can be added without
    // touching the template below.
    const docs = [];
    if (r.nor_url)     docs.push(`<a class="rl-doc-link" data-doc-link href="${esc(r.nor_url)}" target="_blank" rel="noopener" title="Notice of Race">📄 NOR</a>`);
    if (r.si_url)      docs.push(`<a class="rl-doc-link" data-doc-link href="${esc(r.si_url)}"  target="_blank" rel="noopener" title="Sailing Instructions">📄 SI</a>`);
    if (r.website_url) docs.push(`<a class="rl-doc-link" data-doc-link href="${esc(r.website_url)}" target="_blank" rel="noopener" title="Regatta website">🌐 Website</a>`);

    // Subtitle line: venue + boat class + race count, dot-separated.
    const subBits = [];
    if (r.venue)   subBits.push(esc(r.venue));
    if (className) subBits.push(esc(className));
    if (raceCount) subBits.push(`${raceCount} race${raceCount !== 1 ? 's' : ''}`);

    const latest = races.length
        ? `Latest: ${esc(races[races.length - 1].name || 'Race')} · ${esc(fmtShortDate(races[races.length - 1].date))}`
        : 'No races yet';

    // Vertical-stack layout: name, subtitle, docs, latest. The card
    // root MUST be a <div> (not <a>) because the doc chips are also
    // <a> elements — nested anchors are invalid HTML and the browser
    // parser silently closes the outer <a> early, which scatters the
    // chips and Latest line outside the rounded card background.
    // Click navigation is wired in render() via a delegated handler.
    return `
        <div class="rl-card" data-href="./race.html?regatta=${encodeURIComponent(r.regatta_id)}" role="link" tabindex="0">
            <div class="rl-card-name">${esc(r.name)}</div>
            ${subBits.length ? `<div class="rl-card-venue">${subBits.join(' · ')}</div>` : ''}
            ${docs.length ? `<div class="rl-card-docs">${docs.join('')}</div>` : ''}
            <div class="rl-card-latest">${latest}</div>
        </div>
    `;
}

function renderOrphans(container) {
    container.innerHTML = _orphanRaces.map(r => `
        <a class="rl-row" href="./race.html?race=${encodeURIComponent(r.race_id)}">
            <span class="rl-row-date">${esc(fmtShortDate(r.date))}</span>
            <span class="rl-row-name">${esc(r.name || 'Race')}</span>
            <span class="rl-row-cta">Open →</span>
        </a>
    `).join('');
}

function wireToolbar() {
    const search = document.getElementById('rl-search');
    const sort = document.getElementById('rl-sort');
    if (search) search.addEventListener('input', render);
    if (sort)   sort.addEventListener('change', render);
}

document.addEventListener('DOMContentLoaded', init);
