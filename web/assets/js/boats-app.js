// SailFrames boats catalog — browse, edit, photo upload, race history.
// Backend: /api/boats CRUD on api_race lambda. Photos round-trip
// through POST /api/boats/{id}/photo/{slot} (multipart).

const API_BASE = window.SAILFRAMES_API_URL || '';

const state = {
    boats: [],          // index list (summary fields per boat)
    selected: null,     // full boat doc loaded from /api/boats/{id}
    filter: '',
    isNew: false,       // detail pane is editing an unsaved draft
};

function el(id) { return document.getElementById(id); }

function escapeHtml(s) {
    return String(s ?? '').replace(/[&"<>]/g, c =>
        ({ '&': '&amp;', '"': '&quot;', '<': '&lt;', '>': '&gt;' }[c]));
}

function toast(msg, isError = false) {
    const t = el('toast');
    t.textContent = msg;
    t.classList.toggle('error', !!isError);
    t.classList.add('show');
    setTimeout(() => t.classList.remove('show'), 2200);
}

async function api(method, path, body) {
    const init = { method, headers: {} };
    if (body !== undefined) {
        init.headers['Content-Type'] = 'application/json';
        init.body = JSON.stringify(body);
    }
    const resp = await fetch(`${API_BASE}${path}`, init);
    if (!resp.ok) {
        const txt = await resp.text();
        throw new Error(`HTTP ${resp.status}: ${txt}`);
    }
    return resp.json();
}

async function loadBoats() {
    const data = await api('GET', '/api/boats');
    state.boats = data.boats || [];
    renderList();
    el('boats-count').textContent = `${state.boats.length} boat${state.boats.length === 1 ? '' : 's'}`;
}

function renderList() {
    const container = el('boats-list');
    const f = state.filter.toLowerCase();
    const rows = state.boats.filter(b => !f
        || (b.name || '').toLowerCase().includes(f)
        || (b.type || '').toLowerCase().includes(f)
        || String(b.sail_number || '').toLowerCase().includes(f)
        || (b.club || '').toLowerCase().includes(f));

    if (!rows.length) {
        container.innerHTML = '<div class="boats-list-empty">No boats yet — click <strong>+ New Boat</strong> to start.</div>';
        return;
    }

    const selId = state.selected?.boat_id;
    container.innerHTML = rows.map(b => {
        const photo = b.photos?.boat;
        const thumb = photo
            ? `<img class="boat-card-thumb" src="${escapeHtml(photo)}" alt="">`
            : `<div class="boat-card-thumb">⛵</div>`;
        const sub = [b.type, b.sail_number && `#${b.sail_number}`, b.club]
            .filter(Boolean).join(' · ');
        return `
            <div class="boat-card${b.boat_id === selId ? ' active' : ''}" data-id="${escapeHtml(b.boat_id)}">
                ${thumb}
                <div class="boat-card-info">
                    <div class="boat-card-name">${escapeHtml(b.name || '(unnamed)')}</div>
                    <div class="boat-card-sub">${escapeHtml(sub)}</div>
                </div>
            </div>
        `;
    }).join('');

    container.querySelectorAll('.boat-card').forEach(card => {
        card.addEventListener('click', () => selectBoat(card.dataset.id));
    });
}

async function selectBoat(boatId) {
    try {
        state.selected = await api('GET', `/api/boats/${boatId}`);
        state.isNew = false;
        renderList();
        renderDetail();
        loadRaceHistory(boatId);
    } catch (e) {
        toast(`Couldn't load boat: ${e.message}`, true);
    }
}

function startNewBoat() {
    state.selected = {
        boat_id: null,
        name: '',
        type: '',
        sail_number: '',
        club: '',
        loa_m: null,
        skipper: '',
        photos: { boat: null, skipper: null },
        links: [],
        notes: '',
    };
    state.isNew = true;
    renderList();
    renderDetail();
}

function renderDetail() {
    const pane = el('boats-detail');
    if (!state.selected) {
        pane.innerHTML = '<div class="detail-empty">Select a boat from the list, or click <strong>+ New Boat</strong> to add one.</div>';
        return;
    }
    const b = state.selected;
    const photos = b.photos || {};
    const links = b.links || [];

    const photoTile = (slot, label, current) => `
        <label class="photo-tile ${current ? 'has-img' : ''}" data-slot="${slot}">
            ${current
                ? `<img src="${escapeHtml(current)}" alt="${label}">`
                : `<div class="tile-hint">+ Add ${label}<br><small>(JPG/PNG)</small></div>`}
            <span class="tile-label">${label}</span>
            <input type="file" accept="image/*" data-slot="${slot}">
        </label>
    `;

    pane.innerHTML = `
        <div class="detail-header">
            <div class="photo-stack">
                ${photoTile('boat', 'Boat', photos.boat)}
                ${photoTile('skipper', 'Skipper', photos.skipper)}
            </div>
            <div class="detail-meta">
                <div class="form-grid">
                    <div class="form-field full">
                        <label>Boat Name</label>
                        <input type="text" data-field="name" value="${escapeHtml(b.name)}" placeholder="Never Settle">
                    </div>
                    <div class="form-field">
                        <label>Type / Class</label>
                        <input type="text" data-field="type" value="${escapeHtml(b.type)}" placeholder="J/92">
                    </div>
                    <div class="form-field">
                        <label>Sail #</label>
                        <input type="text" data-field="sail_number" value="${escapeHtml(b.sail_number)}" placeholder="USA 14">
                    </div>
                    <div class="form-field">
                        <label>LOA (m)</label>
                        <input type="number" step="0.01" min="0" data-field="loa_m" value="${b.loa_m ?? ''}" placeholder="9.14">
                    </div>
                    <div class="form-field">
                        <label>Yacht Club</label>
                        <input type="text" data-field="club" value="${escapeHtml(b.club)}" placeholder="Constitution YC">
                    </div>
                    <div class="form-field full">
                        <label>Skipper(s) — current series</label>
                        <input type="text" data-field="skipper" value="${escapeHtml(b.skipper)}" placeholder="Robert Pogue">
                    </div>
                    <div class="form-field full">
                        <label>Notes</label>
                        <textarea data-field="notes" rows="2" placeholder="Anything worth remembering about the boat.">${escapeHtml(b.notes)}</textarea>
                    </div>
                </div>
            </div>
        </div>

        <div class="links-section">
            <h2>External links</h2>
            <div class="links-list" id="links-list">
                ${links.map((l, i) => linkRowHtml(l, i)).join('')}
            </div>
            <button type="button" class="btn-add-link" id="btn-add-link">+ Add link</button>
        </div>

        <div class="races-section">
            <h2>Race history</h2>
            <div id="races-history"><div class="races-empty">${state.isNew ? 'Save the boat first to load history.' : 'Loading…'}</div></div>
        </div>

        <div class="detail-actions">
            ${state.isNew
                ? '<button class="btn-secondary" id="btn-cancel-new">Cancel</button>'
                : '<button class="btn-danger" id="btn-delete-boat">Delete boat</button>'}
            <div class="spacer"></div>
            <button class="btn-primary" id="btn-save-boat">${state.isNew ? 'Create boat' : 'Save changes'}</button>
        </div>
    `;

    // Field listeners — push into state.selected on every change
    pane.querySelectorAll('[data-field]').forEach(input => {
        input.addEventListener('input', () => {
            const field = input.dataset.field;
            let v = input.value;
            if (field === 'loa_m') v = v === '' ? null : Number(v);
            state.selected[field] = v;
        });
    });

    // Photo upload listeners
    pane.querySelectorAll('input[type=file][data-slot]').forEach(inp => {
        inp.addEventListener('change', async (e) => {
            const file = e.target.files?.[0];
            const slot = inp.dataset.slot;
            if (!file) return;
            if (state.isNew || !state.selected.boat_id) {
                toast('Save the boat first, then add photos.', true);
                inp.value = '';
                return;
            }
            await uploadPhoto(state.selected.boat_id, slot, file);
        });
    });

    // Links
    pane.querySelectorAll('.link-row [data-link-field]').forEach(input => {
        input.addEventListener('input', () => {
            const idx = Number(input.closest('.link-row').dataset.idx);
            const field = input.dataset.linkField;
            if (!state.selected.links[idx]) state.selected.links[idx] = { label: '', url: '' };
            state.selected.links[idx][field] = input.value;
        });
    });
    pane.querySelectorAll('.btn-link-remove').forEach(btn => {
        btn.addEventListener('click', () => {
            const idx = Number(btn.closest('.link-row').dataset.idx);
            state.selected.links.splice(idx, 1);
            renderDetail();
        });
    });
    el('btn-add-link')?.addEventListener('click', () => {
        state.selected.links = state.selected.links || [];
        state.selected.links.push({ label: '', url: '' });
        renderDetail();
    });

    // Buttons
    el('btn-save-boat')?.addEventListener('click', saveBoat);
    el('btn-cancel-new')?.addEventListener('click', () => {
        state.selected = null;
        state.isNew = false;
        renderList();
        renderDetail();
    });
    el('btn-delete-boat')?.addEventListener('click', deleteBoat);

    if (!state.isNew && state.selected.boat_id) loadRaceHistory(state.selected.boat_id);
}

function linkRowHtml(link, idx) {
    return `
        <div class="link-row" data-idx="${idx}">
            <input type="text" data-link-field="label" value="${escapeHtml(link.label || '')}" placeholder="Label (Website, Class Assoc...)">
            <input type="url" data-link-field="url" value="${escapeHtml(link.url || '')}" placeholder="https://…">
            <button type="button" class="btn-link-remove" title="Remove link">×</button>
        </div>
    `;
}

async function loadRaceHistory(boatId) {
    const container = el('races-history');
    if (!container) return;
    try {
        const data = await api('GET', `/api/boats/${boatId}/races`);
        const races = data.races || [];
        if (!races.length) {
            container.innerHTML = '<div class="races-empty">No races yet — this boat hasn\'t been assigned to a race.</div>';
            return;
        }
        container.innerHTML = `
            <table class="races-table">
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Race</th>
                        <th>Class</th>
                        <th>Rating</th>
                        <th>Place</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    ${races.map(r => `
                        <tr>
                            <td>${escapeHtml(r.date || '—')}</td>
                            <td><a href="/race.html?race=${escapeHtml(r.race_id)}">${escapeHtml(r.name || r.race_id)}</a></td>
                            <td>${escapeHtml(r.class || '—')}</td>
                            <td>${r.rating != null ? Number(r.rating).toFixed(3) : '—'}</td>
                            <td>${r.place != null ? r.place : '—'}</td>
                            <td>${escapeHtml(r.finish_status || '—')}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    } catch (e) {
        container.innerHTML = `<div class="races-empty">Couldn't load history: ${escapeHtml(e.message)}</div>`;
    }
}

async function saveBoat() {
    const b = state.selected;
    if (!b.name?.trim()) { toast('Boat name is required.', true); return; }
    // Filter out empty links so we don't save blanks
    b.links = (b.links || []).filter(l => l.label?.trim() || l.url?.trim());
    try {
        let saved;
        if (state.isNew) {
            saved = await api('POST', '/api/boats', b);
            toast('Boat created.');
        } else {
            saved = await api('PATCH', `/api/boats/${b.boat_id}`, b);
            toast('Saved.');
        }
        state.selected = saved;
        state.isNew = false;
        await loadBoats();
        renderDetail();
    } catch (e) {
        toast(`Save failed: ${e.message}`, true);
    }
}

async function deleteBoat() {
    const b = state.selected;
    if (!confirm(`Delete ${b.name}? This removes the boat from the catalog. Races already referencing it will still display via their embedded fallback metadata.`)) return;
    try {
        await api('DELETE', `/api/boats/${b.boat_id}`);
        toast('Deleted.');
        state.selected = null;
        await loadBoats();
        renderDetail();
    } catch (e) {
        toast(`Delete failed: ${e.message}`, true);
    }
}

async function uploadPhoto(boatId, slot, file) {
    const fd = new FormData();
    fd.append('file', file);
    try {
        const resp = await fetch(`${API_BASE}/api/boats/${boatId}/photo/${slot}`, {
            method: 'POST',
            body: fd,
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}: ${await resp.text()}`);
        const data = await resp.json();
        if (!state.selected.photos) state.selected.photos = {};
        state.selected.photos[slot] = data.url;
        // Refresh the catalog index so the thumbnail appears in the list immediately
        await loadBoats();
        renderDetail();
        toast(`${slot} photo uploaded.`);
    } catch (e) {
        toast(`Photo upload failed: ${e.message}`, true);
    }
}

// --- init ---

el('boats-search').addEventListener('input', (e) => {
    state.filter = e.target.value;
    renderList();
});
el('btn-new-boat').addEventListener('click', startNewBoat);

loadBoats().catch(e => toast(`Failed to load: ${e.message}`, true));

// Deep link: ?boat=<id> auto-opens a boat
try {
    const u = new URL(location.href);
    const bid = u.searchParams.get('boat');
    if (bid) selectBoat(bid);
} catch {}
