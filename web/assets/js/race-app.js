/**
 * Race Dashboard Application
 *
 * Main controller for the multi-boat race dashboard.
 * Handles race selection, data loading, map visualization,
 * and playback controls.
 */

// Configuration
const API_BASE = window.location.origin;
const BOAT_COLORS = {
    'E1': '#1d9bf0',  // Blue
    'E2': '#f59e0b',  // Orange
    'E3': '#00ba7c',  // Green
    'E4': '#f4212e',  // Red
    'E5': '#a855f7',  // Purple
    'E6': '#22d3ee',  // Cyan
};

// State
let regattas = [];
let races = [];
let currentRace = null;
let raceData = null;
let map = null;
let boatLayers = {};  // device_id -> { track, marker }
let isPlaying = false;
let playbackSpeed = 1;
let currentTime = 0;  // seconds from race start
let raceDuration = 0;
let playbackInterval = null;
let speedChart = null;

// Initialize
document.addEventListener('DOMContentLoaded', init);

async function init() {
    console.log('[Race] Initializing race dashboard...');

    // Initialize map
    initMap();

    // Initialize chart
    initSpeedChart();

    // Load data
    await loadRegattas();
    await loadRaces();

    // Setup event listeners
    setupEventListeners();

    console.log('[Race] Dashboard ready');
}

// --- Map ---

function initMap() {
    map = L.map('race-map', {
        center: [42.36, -71.05],  // Boston Harbor
        zoom: 14,
        zoomControl: true,
    });

    // Dark tile layer
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; OpenStreetMap, &copy; CARTO',
        maxZoom: 19,
    }).addTo(map);
}

function clearBoatLayers() {
    for (const deviceId of Object.keys(boatLayers)) {
        if (boatLayers[deviceId].track) {
            map.removeLayer(boatLayers[deviceId].track);
        }
        if (boatLayers[deviceId].marker) {
            map.removeLayer(boatLayers[deviceId].marker);
        }
    }
    boatLayers = {};
}

function addBoatTrack(deviceId, gpsData, boat) {
    const color = BOAT_COLORS[deviceId] || '#888888';

    // Create track polyline
    const coords = gpsData.map(p => [p.lat, p.lon]);
    const track = L.polyline(coords, {
        color: color,
        weight: 3,
        opacity: 0.8,
    }).addTo(map);

    // Create boat marker (triangle pointing in direction of travel)
    const marker = L.circleMarker([0, 0], {
        radius: 8,
        color: color,
        fillColor: color,
        fillOpacity: 1,
        weight: 2,
    }).addTo(map);

    boatLayers[deviceId] = {
        track,
        marker,
        data: gpsData,
        boat,
        visible: true,
    };
}

function updateBoatPositions(timeSeconds) {
    for (const [deviceId, layer] of Object.entries(boatLayers)) {
        if (!layer.visible || !layer.data.length) continue;

        // Find position at current time
        const startTime = new Date(currentRace.start_time).getTime();
        const targetTime = startTime + timeSeconds * 1000;

        // Find closest data point
        let closest = layer.data[0];
        let minDiff = Infinity;

        for (const point of layer.data) {
            const pointTime = new Date(point.t).getTime();
            const diff = Math.abs(pointTime - targetTime);
            if (diff < minDiff) {
                minDiff = diff;
                closest = point;
            }
        }

        // Update marker position
        if (closest && closest.lat && closest.lon) {
            layer.marker.setLatLng([closest.lat, closest.lon]);

            // Update legend with current speed
            updateLegendSpeed(deviceId, closest.speed_kn || 0);
        }
    }
}

function fitMapToBounds() {
    const allCoords = [];
    for (const layer of Object.values(boatLayers)) {
        if (layer.data) {
            for (const p of layer.data) {
                if (p.lat && p.lon) {
                    allCoords.push([p.lat, p.lon]);
                }
            }
        }
    }

    if (allCoords.length > 0) {
        const bounds = L.latLngBounds(allCoords);
        map.fitBounds(bounds, { padding: [50, 50] });
    }
}

// --- Boat Legend ---

function renderBoatLegend() {
    const container = document.getElementById('boat-legend');
    container.innerHTML = '';

    if (!currentRace || !currentRace.boats) return;

    for (const boat of currentRace.boats) {
        const deviceId = boat.device_id;
        const color = BOAT_COLORS[deviceId] || '#888888';
        const hasData = boatLayers[deviceId]?.data?.length > 0;

        const item = document.createElement('div');
        item.className = `boat-legend-item ${hasData ? '' : 'disabled'}`;
        item.dataset.deviceId = deviceId;
        item.innerHTML = `
            <span class="boat-color-dot" style="background: ${color}"></span>
            <span class="boat-legend-name">${boat.boat_name || deviceId}</span>
            <span class="boat-legend-speed" id="legend-speed-${deviceId}">-- kn</span>
        `;

        // Toggle visibility on click
        item.addEventListener('click', () => {
            if (!hasData) return;
            toggleBoatVisibility(deviceId);
            item.classList.toggle('disabled');
        });

        container.appendChild(item);
    }
}

function updateLegendSpeed(deviceId, speed) {
    const el = document.getElementById(`legend-speed-${deviceId}`);
    if (el) {
        el.textContent = `${speed.toFixed(1)} kn`;
    }
}

function toggleBoatVisibility(deviceId) {
    const layer = boatLayers[deviceId];
    if (!layer) return;

    layer.visible = !layer.visible;

    if (layer.visible) {
        layer.track.addTo(map);
        layer.marker.addTo(map);
    } else {
        map.removeLayer(layer.track);
        map.removeLayer(layer.marker);
    }
}

// --- Leaderboard ---

function renderLeaderboard() {
    const container = document.getElementById('leaderboard');

    if (!currentRace || !raceData) {
        container.innerHTML = '<div class="leaderboard-empty">Select a race to view standings</div>';
        return;
    }

    // Get current positions based on distance or speed
    const positions = calculatePositions();

    container.innerHTML = positions.map((item, index) => {
        const pos = index + 1;
        const color = BOAT_COLORS[item.deviceId] || '#888888';
        const posClass = pos <= 3 ? `p${pos}` : '';

        return `
            <div class="leaderboard-item">
                <div class="leaderboard-position ${posClass}">${pos}</div>
                <div class="leaderboard-boat-color" style="background: ${color}"></div>
                <div class="leaderboard-boat-info">
                    <div class="leaderboard-boat-name">${item.boatName}</div>
                    <div class="leaderboard-boat-device">${item.deviceId}</div>
                </div>
                <div class="leaderboard-stats">
                    <div class="leaderboard-speed">${item.speed.toFixed(1)} kn</div>
                    <div class="leaderboard-delta">${item.delta}</div>
                </div>
            </div>
        `;
    }).join('');
}

function calculatePositions() {
    if (!raceData?.boats) return [];

    const positions = [];

    for (const [deviceId, boatData] of Object.entries(raceData.boats)) {
        if (boatData.error || !boatData.sensors?.gps?.length) continue;

        const layer = boatLayers[deviceId];
        const boat = boatData.boat;

        // Get current speed from most recent position
        const gps = boatData.sensors.gps;
        const lastPoint = gps[gps.length - 1];

        positions.push({
            deviceId,
            boatName: boat?.boat_name || deviceId,
            speed: lastPoint?.speed_kn || 0,
            delta: '',  // TODO: calculate time delta
        });
    }

    // Sort by speed (descending) for now
    // TODO: Sort by actual race position (distance to finish, etc.)
    positions.sort((a, b) => b.speed - a.speed);

    // Add deltas
    if (positions.length > 0) {
        const leader = positions[0];
        for (let i = 1; i < positions.length; i++) {
            const diff = leader.speed - positions[i].speed;
            positions[i].delta = diff > 0 ? `-${diff.toFixed(1)} kn` : '';
        }
    }

    return positions;
}

// --- Speed Chart ---

function initSpeedChart() {
    const ctx = document.getElementById('speed-chart').getContext('2d');

    speedChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                intersect: false,
                mode: 'index',
            },
            plugins: {
                legend: {
                    display: false,
                },
            },
            scales: {
                x: {
                    display: false,
                },
                y: {
                    title: {
                        display: true,
                        text: 'Speed (kn)',
                        color: '#888',
                    },
                    grid: {
                        color: 'rgba(255,255,255,0.1)',
                    },
                    ticks: {
                        color: '#888',
                    },
                },
            },
        },
    });
}

function updateSpeedChart() {
    if (!raceData?.boats || !speedChart) return;

    const datasets = [];
    const togglesContainer = document.getElementById('speed-chart-toggles');
    togglesContainer.innerHTML = '';

    for (const [deviceId, boatData] of Object.entries(raceData.boats)) {
        if (boatData.error || !boatData.sensors?.gps?.length) continue;

        const color = BOAT_COLORS[deviceId] || '#888888';
        const gps = boatData.sensors.gps;

        // Downsample for chart performance
        const step = Math.max(1, Math.floor(gps.length / 200));
        const data = [];

        for (let i = 0; i < gps.length; i += step) {
            data.push({
                x: i,
                y: gps[i].speed_kn || 0,
            });
        }

        datasets.push({
            label: deviceId,
            data,
            borderColor: color,
            backgroundColor: color + '20',
            borderWidth: 2,
            pointRadius: 0,
            tension: 0.2,
        });

        // Add toggle button
        const toggle = document.createElement('button');
        toggle.className = 'chart-toggle';
        toggle.style.borderColor = color;
        toggle.style.background = color;
        toggle.title = deviceId;
        toggle.addEventListener('click', () => {
            const dataset = speedChart.data.datasets.find(d => d.label === deviceId);
            if (dataset) {
                dataset.hidden = !dataset.hidden;
                toggle.classList.toggle('disabled', dataset.hidden);
                speedChart.update();
            }
        });
        togglesContainer.appendChild(toggle);
    }

    speedChart.data.datasets = datasets;
    speedChart.update();
}

// --- Playback ---

function setupPlaybackControls() {
    const playBtn = document.getElementById('btn-play');
    const slider = document.getElementById('timeline-slider');
    const speedSelect = document.getElementById('playback-speed');

    playBtn.addEventListener('click', togglePlayback);

    slider.addEventListener('input', (e) => {
        const position = parseInt(e.target.value) / 1000;
        seekTo(position);
    });

    speedSelect.addEventListener('change', (e) => {
        playbackSpeed = parseFloat(e.target.value);
    });

    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;

        if (e.code === 'Space') {
            e.preventDefault();
            togglePlayback();
        } else if (e.code === 'ArrowLeft') {
            seekTo(Math.max(0, currentTime / raceDuration - 0.01));
        } else if (e.code === 'ArrowRight') {
            seekTo(Math.min(1, currentTime / raceDuration + 0.01));
        }
    });
}

function togglePlayback() {
    isPlaying = !isPlaying;
    const playBtn = document.getElementById('btn-play');
    playBtn.textContent = isPlaying ? '⏸' : '▶';

    if (isPlaying) {
        startPlayback();
    } else {
        stopPlayback();
    }
}

function startPlayback() {
    if (playbackInterval) clearInterval(playbackInterval);

    playbackInterval = setInterval(() => {
        currentTime += 0.1 * playbackSpeed;

        if (currentTime >= raceDuration) {
            currentTime = 0;
            stopPlayback();
            return;
        }

        updatePlaybackPosition();
    }, 100);
}

function stopPlayback() {
    isPlaying = false;
    document.getElementById('btn-play').textContent = '▶';
    if (playbackInterval) {
        clearInterval(playbackInterval);
        playbackInterval = null;
    }
}

function seekTo(position) {
    currentTime = position * raceDuration;
    updatePlaybackPosition();
}

function updatePlaybackPosition() {
    // Update slider
    const slider = document.getElementById('timeline-slider');
    slider.value = (currentTime / raceDuration) * 1000;

    // Update time display
    document.getElementById('time-current').textContent = formatTime(currentTime);
    document.getElementById('elapsed-time').textContent = formatTime(currentTime);

    // Update boat positions on map
    updateBoatPositions(currentTime);

    // Update leaderboard
    renderLeaderboard();
}

function formatTime(seconds) {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
}

// --- Data Loading ---

async function loadRegattas() {
    try {
        const resp = await fetch(`${API_BASE}/api/regattas`);
        const data = await resp.json();
        regattas = data.regattas || [];

        // Populate regatta selects
        const regattaSelect = document.getElementById('regatta-select');
        const regattaInput = document.getElementById('regatta-input');

        const options = regattas.map(r =>
            `<option value="${r.regatta_id}">${r.name}</option>`
        ).join('');

        regattaSelect.innerHTML = '<option value="">All Regattas</option>' + options;
        regattaInput.innerHTML = '<option value="">None</option>' + options;

    } catch (err) {
        console.error('[Race] Failed to load regattas:', err);
    }
}

async function loadRaces(regattaId = null) {
    try {
        let url = `${API_BASE}/api/races`;
        if (regattaId) {
            url += `?regatta_id=${regattaId}`;
        }

        const resp = await fetch(url);
        const data = await resp.json();
        races = data.races || [];

        // Populate race select
        const raceSelect = document.getElementById('race-select');
        raceSelect.innerHTML = '<option value="">Select a race...</option>' +
            races.map(r =>
                `<option value="${r.race_id}">${r.name} (${r.date})</option>`
            ).join('');

    } catch (err) {
        console.error('[Race] Failed to load races:', err);
    }
}

async function loadRaceData(raceId) {
    try {
        // Load race definition
        const raceResp = await fetch(`${API_BASE}/api/races/${raceId}`);
        currentRace = await raceResp.json();

        // Update UI
        document.getElementById('race-name').textContent = currentRace.name;
        document.getElementById('race-time').textContent =
            `${currentRace.date} ${currentRace.start_time.split('T')[1]?.slice(0, 5) || ''}`;
        document.getElementById('btn-edit-race').disabled = false;

        // Load sensor data for all boats
        const dataResp = await fetch(`${API_BASE}/api/races/${raceId}/data?sensors=gps,imu,wind`);
        raceData = await dataResp.json();

        // Calculate race duration
        const start = new Date(currentRace.start_time).getTime();
        const end = new Date(currentRace.end_time).getTime();
        raceDuration = (end - start) / 1000;

        // Update time display
        document.getElementById('time-total').textContent = formatTime(raceDuration);

        // Clear existing layers and add new ones
        clearBoatLayers();

        for (const [deviceId, boatData] of Object.entries(raceData.boats)) {
            if (boatData.error || !boatData.sensors?.gps?.length) {
                console.warn(`[Race] No data for ${deviceId}:`, boatData.error);
                continue;
            }

            addBoatTrack(deviceId, boatData.sensors.gps, boatData.boat);
        }

        // Fit map to show all tracks
        fitMapToBounds();

        // Render legend and leaderboard
        renderBoatLegend();
        renderLeaderboard();

        // Update speed chart
        updateSpeedChart();

        // Reset playback
        currentTime = 0;
        updatePlaybackPosition();

        console.log('[Race] Loaded race data:', currentRace.name);

    } catch (err) {
        console.error('[Race] Failed to load race data:', err);
        alert('Failed to load race data. Check console for details.');
    }
}

// --- Race Editor Modal ---

function openRaceModal(race = null) {
    const modal = document.getElementById('race-modal');
    const title = document.getElementById('modal-title');

    if (race) {
        title.textContent = 'Edit Race';
        populateRaceForm(race);
    } else {
        title.textContent = 'New Race';
        clearRaceForm();
    }

    modal.style.display = 'flex';
}

function closeRaceModal() {
    document.getElementById('race-modal').style.display = 'none';
}

function clearRaceForm() {
    document.getElementById('race-name-input').value = '';
    document.getElementById('race-date-input').value = new Date().toISOString().split('T')[0];
    document.getElementById('start-time-input').value = '18:00';
    document.getElementById('end-time-input').value = '18:30';
    document.getElementById('regatta-input').value = '';

    // Default boat assignments
    renderBoatAssignments([
        { device_id: 'E1', boat_name: '', sail_number: '' },
        { device_id: 'E2', boat_name: '', sail_number: '' },
        { device_id: 'E3', boat_name: '', sail_number: '' },
        { device_id: 'E4', boat_name: '', sail_number: '' },
        { device_id: 'E5', boat_name: '', sail_number: '' },
        { device_id: 'E6', boat_name: '', sail_number: '' },
    ]);
}

function populateRaceForm(race) {
    document.getElementById('race-name-input').value = race.name || '';
    document.getElementById('race-date-input').value = race.date || '';
    document.getElementById('start-time-input').value = race.start_time?.split('T')[1]?.slice(0, 8) || '';
    document.getElementById('end-time-input').value = race.end_time?.split('T')[1]?.slice(0, 8) || '';
    document.getElementById('regatta-input').value = race.regatta_id || '';

    renderBoatAssignments(race.boats || []);
    renderFinishOrder(race.finish_order || [], race.boats || []);
}

function renderBoatAssignments(boats) {
    const container = document.getElementById('boat-assignments');

    // Ensure all 6 devices
    const allDevices = ['E1', 'E2', 'E3', 'E4', 'E5', 'E6'];
    const boatMap = {};
    for (const b of boats) {
        boatMap[b.device_id] = b;
    }

    container.innerHTML = allDevices.map(deviceId => {
        const boat = boatMap[deviceId] || { device_id: deviceId, boat_name: '', sail_number: '' };
        const color = BOAT_COLORS[deviceId];
        const matched = boat.session_path ? 'matched' : '';
        const status = boat.session_path ? 'Session matched' : 'No session';

        return `
            <div class="boat-assignment" data-device="${deviceId}">
                <div class="boat-assignment-device">
                    <span class="boat-assignment-color" style="background: ${color}"></span>
                    <span>${deviceId}</span>
                </div>
                <input type="text" placeholder="Boat name" value="${boat.boat_name || ''}" data-field="boat_name">
                <input type="text" placeholder="Sail #" value="${boat.sail_number || ''}" data-field="sail_number">
                <span class="boat-assignment-status ${matched}">${status}</span>
            </div>
        `;
    }).join('');
}

function renderFinishOrder(order, boats) {
    const container = document.getElementById('finish-order');

    // Build list of boats with positions
    const boatMap = {};
    for (const b of boats) {
        boatMap[b.device_id] = b;
    }

    // Use order if provided, otherwise use boats array order
    const orderedDevices = order.length > 0 ? order : boats.map(b => b.device_id);

    container.innerHTML = orderedDevices.map((deviceId, index) => {
        const boat = boatMap[deviceId] || { device_id: deviceId, boat_name: deviceId };
        const color = BOAT_COLORS[deviceId];

        return `
            <div class="finish-order-item" draggable="true" data-device="${deviceId}">
                <span class="finish-order-position">${index + 1}</span>
                <div class="finish-order-boat">
                    <span class="boat-assignment-color" style="background: ${color}"></span>
                    <span>${boat.boat_name || deviceId}</span>
                </div>
            </div>
        `;
    }).join('');

    // Setup drag and drop
    setupFinishOrderDragDrop();
}

function setupFinishOrderDragDrop() {
    const container = document.getElementById('finish-order');
    let draggedItem = null;

    container.querySelectorAll('.finish-order-item').forEach(item => {
        item.addEventListener('dragstart', () => {
            draggedItem = item;
            item.style.opacity = '0.5';
        });

        item.addEventListener('dragend', () => {
            draggedItem = null;
            item.style.opacity = '1';
            updateFinishOrderPositions();
        });

        item.addEventListener('dragover', (e) => {
            e.preventDefault();
            const afterElement = getDragAfterElement(container, e.clientY);
            if (afterElement == null) {
                container.appendChild(draggedItem);
            } else {
                container.insertBefore(draggedItem, afterElement);
            }
        });
    });
}

function getDragAfterElement(container, y) {
    const elements = [...container.querySelectorAll('.finish-order-item:not(.dragging)')];

    return elements.reduce((closest, child) => {
        const box = child.getBoundingClientRect();
        const offset = y - box.top - box.height / 2;
        if (offset < 0 && offset > closest.offset) {
            return { offset, element: child };
        } else {
            return closest;
        }
    }, { offset: Number.NEGATIVE_INFINITY }).element;
}

function updateFinishOrderPositions() {
    const items = document.querySelectorAll('.finish-order-item');
    items.forEach((item, index) => {
        item.querySelector('.finish-order-position').textContent = index + 1;
    });
}

function getFormData() {
    const date = document.getElementById('race-date-input').value;
    const startTime = document.getElementById('start-time-input').value;
    const endTime = document.getElementById('end-time-input').value;

    // Build boats array from form
    const boats = [];
    document.querySelectorAll('.boat-assignment').forEach(row => {
        const deviceId = row.dataset.device;
        const boatName = row.querySelector('[data-field="boat_name"]').value;
        const sailNumber = row.querySelector('[data-field="sail_number"]').value;

        if (boatName || sailNumber) {
            boats.push({
                device_id: deviceId,
                boat_name: boatName,
                sail_number: sailNumber,
            });
        }
    });

    // Get finish order
    const finishOrder = [];
    document.querySelectorAll('.finish-order-item').forEach(item => {
        finishOrder.push(item.dataset.device);
    });

    return {
        name: document.getElementById('race-name-input').value,
        date: date,
        start_time: `${date}T${startTime}:00Z`,
        end_time: `${date}T${endTime}:00Z`,
        regatta_id: document.getElementById('regatta-input').value || null,
        boats,
        finish_order: finishOrder,
    };
}

async function saveRace() {
    const formData = getFormData();

    try {
        let resp;
        if (currentRace?.race_id) {
            // Update existing
            resp = await fetch(`${API_BASE}/api/races/${currentRace.race_id}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(formData),
            });
        } else {
            // Create new
            resp = await fetch(`${API_BASE}/api/races`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(formData),
            });
        }

        if (!resp.ok) {
            throw new Error(`HTTP ${resp.status}`);
        }

        const savedRace = await resp.json();
        console.log('[Race] Saved race:', savedRace);

        closeRaceModal();
        await loadRaces();

        // Load the saved race
        document.getElementById('race-select').value = savedRace.race_id;
        await loadRaceData(savedRace.race_id);

    } catch (err) {
        console.error('[Race] Failed to save race:', err);
        alert('Failed to save race. Check console for details.');
    }
}

async function matchSessions() {
    if (!currentRace?.race_id) {
        alert('Save the race first before matching sessions.');
        return;
    }

    try {
        const resp = await fetch(`${API_BASE}/api/races/${currentRace.race_id}/match-sessions`, {
            method: 'POST',
        });

        const result = await resp.json();
        console.log('[Race] Matched sessions:', result);

        // Reload race to get updated session paths
        const raceResp = await fetch(`${API_BASE}/api/races/${currentRace.race_id}`);
        const updatedRace = await raceResp.json();

        renderBoatAssignments(updatedRace.boats || []);

        alert(`Matched ${result.matched.filter(m => m.session_path).length} sessions.`);

    } catch (err) {
        console.error('[Race] Failed to match sessions:', err);
        alert('Failed to match sessions. Check console for details.');
    }
}

// --- Event Listeners ---

function setupEventListeners() {
    // Regatta filter
    document.getElementById('regatta-select').addEventListener('change', (e) => {
        loadRaces(e.target.value || null);
    });

    // Race selection
    document.getElementById('race-select').addEventListener('change', (e) => {
        if (e.target.value) {
            loadRaceData(e.target.value);
        }
    });

    // New race button
    document.getElementById('btn-new-race').addEventListener('click', () => {
        currentRace = null;
        openRaceModal();
    });

    // Edit race button
    document.getElementById('btn-edit-race').addEventListener('click', () => {
        if (currentRace) {
            openRaceModal(currentRace);
        }
    });

    // Modal controls
    document.getElementById('modal-close').addEventListener('click', closeRaceModal);
    document.getElementById('btn-cancel').addEventListener('click', closeRaceModal);
    document.getElementById('btn-save-race').addEventListener('click', saveRace);
    document.getElementById('btn-match-sessions').addEventListener('click', matchSessions);

    // Close modal on backdrop click
    document.querySelector('.modal-backdrop').addEventListener('click', closeRaceModal);

    // Playback controls
    setupPlaybackControls();
}
