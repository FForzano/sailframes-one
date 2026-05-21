/**
 * SailFrames Analytics Application
 * Main entry point that coordinates all components
 */

// Check if user is authenticated via Cloudflare Access
function isAdmin() {
    return document.cookie.includes('CF_Authorization');
}
const IS_ADMIN = isAdmin();

// API base URL - will be set by config or use relative path
// For S3 hosting, this will be injected as window.SAILFRAMES_API_URL
const API_BASE = window.SAILFRAMES_API_URL || '';

// Global component instances
let mapView = null;
let chartPanel = null;
let videoPlayer = null;
let timeline = null;

// Current session
let currentSession = null;
let currentDeviceId = null;
let currentSessionDate = null;

/**
 * Initialize the application
 */
async function init() {
    console.log('Initializing SailFrames Analytics...');

    // Initialize components
    mapView = new MapView('map');
    chartPanel = new ChartPanel();
    videoPlayer = new VideoPlayer();
    timeline = new Timeline();

    // Expose components globally for cross-component communication
    window.timeline = timeline;
    window.mapView = mapView;
    window.videoPlayer = videoPlayer;

    // Check for ?session= URL parameter first (e.g., ?session=E1/2026-04-04-s013-000013)
    const urlParams = new URLSearchParams(window.location.search);
    const sessionParam = urlParams.get('session');

    // Load sessions list (but don't auto-select if URL param exists)
    await loadSessions(!sessionParam);

    // Setup session selector
    const sessionSelect = document.getElementById('session-select');
    sessionSelect.addEventListener('change', (e) => {
        if (e.target.value) {
            const [deviceId, ...dateParts] = e.target.value.split('/');
            const date = dateParts.join('/');
            loadSession(deviceId, date);
        }
    });

    // Load session from URL parameter if present
    if (sessionParam) {
        const slashIndex = sessionParam.indexOf('/');
        if (slashIndex !== -1) {
            const deviceId = sessionParam.substring(0, slashIndex);
            const date = sessionParam.substring(slashIndex + 1);
            console.log(`Loading session from URL: ${deviceId}/${date}`);
            sessionSelect.value = sessionParam;
            loadSession(deviceId, date);
        }
    }

    // Setup save metadata button
    const btnSaveMeta = document.getElementById('btn-save-meta');
    if (btnSaveMeta) {
        btnSaveMeta.addEventListener('click', saveSessionMeta);
    }

    // Setup track layer toggle (single button; PPK + decimated-10Hz buttons
    // retired with firmware .09 — nav.csv is natively 10 Hz now)
    const gpsToggle = document.getElementById('toggle-gps-track');
    if (gpsToggle) {
        gpsToggle.addEventListener('click', () => {
            gpsToggle.classList.toggle('active');
            mapView.toggleGPS(gpsToggle.classList.contains('active'));
        });
    }

    // Setup cleanup button (admin only)
    const btnCleanup = document.getElementById('btn-cleanup');
    if (btnCleanup) {
        if (IS_ADMIN) {
            btnCleanup.addEventListener('click', cleanupSessions);
        } else {
            btnCleanup.style.display = 'none';
        }
    }

    // Setup map expand button
    const btnExpand = document.getElementById('btn-expand-map');
    const mapPanel = document.getElementById('map-panel');

    if (btnExpand && mapPanel) {
        btnExpand.addEventListener('click', () => {
            const isExpanded = mapPanel.classList.toggle('expanded');
            document.body.classList.toggle('map-expanded');
            // Update button text
            btnExpand.textContent = isExpanded ? '⤡' : '⤢';
            btnExpand.title = isExpanded ? 'Exit fullscreen' : 'Expand map to fullscreen';
            // Trigger map resize after expansion
            setTimeout(() => {
                if (mapView && mapView.map) {
                    mapView.map.invalidateSize();
                }
            }, 350);
        });
    }

    console.log('Initialization complete');
}

/**
 * Load available sessions
 * @param {boolean} autoSelect - Whether to auto-select and load first session
 */
async function loadSessions(autoSelect = true) {
    try {
        const response = await fetch(`${API_BASE}/api/sessions`);
        if (!response.ok) throw new Error('Failed to fetch sessions');

        const data = await response.json();
        const sessions = data.sessions || [];

        const select = document.getElementById('session-select');

        // Clear existing options (keep placeholder)
        while (select.options.length > 1) {
            select.remove(1);
        }

        // Add session options with session_id for E1 sessions
        sessions.forEach(session => {
            const option = document.createElement('option');
            // Include session_id in value for proper matching
            const sessionPath = session.session_id
                ? `${session.date}-${session.session_id}`
                : session.date;
            option.value = `${session.device_id}/${sessionPath}`;

            const duration = session.duration_minutes
                ? ` (${session.duration_minutes} min)`
                : '';
            const video = session.has_video ? ' [VIDEO]' : '';

            option.textContent = `${session.date}${session.session_id ? '-' + session.session_id : ''}${duration}${video}`;
            select.appendChild(option);
        });

        // Auto-select first session if requested and available
        if (autoSelect && sessions.length > 0) {
            const first = sessions[0];
            const firstPath = first.session_id
                ? `${first.date}-${first.session_id}`
                : first.date;
            select.value = `${first.device_id}/${firstPath}`;
            loadSession(first.device_id, firstPath);
        }
    } catch (error) {
        console.error('Error loading sessions:', error);
    }
}

/**
 * Load a specific session
 */
async function loadSession(deviceId, date) {
    console.log(`Loading session: ${deviceId}/${date}`);
    showLoading(true);

    // Store current session info for saving
    currentDeviceId = deviceId;
    currentSessionDate = date;

    try {
        // Load session data (1Hz sensors for charts — PPK loaded separately for map)
        const response = await fetch(
            `${API_BASE}/api/data/${deviceId}/${date}?sensors=gps,imu,wind,pressure`
        );

        if (!response.ok) throw new Error('Failed to fetch session data');

        const sessionData = await response.json();
        currentSession = sessionData;

        // Update session meta UI
        updateSessionMetaUI(sessionData);

        // Extract GPS data for map
        const gpsData = sessionData.data
            .filter(p => p.gps)
            .map(p => ({
                t: p.t,
                lat: p.gps.lat,
                lon: p.gps.lon,
                speed_kn: p.gps.speed_kn,
                course: p.gps.course,
                fix: p.gps.fix,
                sats: p.gps.sats
            }));

        // Extract wind data for map overlay
        const windData = sessionData.data
            .filter(p => p.wind)
            .map(p => ({
                t: p.t,
                awa: p.wind.awa,
                aws_kn: p.wind.aws_kn
            }));

        // Update components
        mapView.setData(gpsData);
        mapView.setWindData(windData);
        chartPanel.setData(sessionData);

        // PPK / 10 Hz dedicated fetches retired with firmware 2026.05.20.09 —
        // nav.csv is now natively 10 Hz, so a single GPS track is the whole
        // story. See docs/RTCM_PPK_ARCHIVE.md for the previous PPK pipeline.

        // Fetch NOAA buoy data for session time range
        await loadBuoyData(sessionData.start_time, sessionData.end_time);

        // Set time controller bounds (with optional trim)
        if (sessionData.start_time && sessionData.end_time) {
            window.timeController.setSession(
                sessionData.start_time,
                sessionData.end_time,
                sessionData.trim || null
            );
        }

        // Set session info for timeline trim controls
        if (timeline && timeline.setSessionInfo) {
            timeline.setSessionInfo(deviceId, date);
        }

        // Load video streams
        await videoPlayer.loadStreams(deviceId, date);

        console.log(`Loaded ${sessionData.sample_count} data points`);
    } catch (error) {
        console.error('Error loading session:', error);
    } finally {
        showLoading(false);
    }
}

/**
 * Show/hide loading overlay
 */
function showLoading(show) {
    const overlay = document.getElementById('loading');
    overlay.style.display = show ? 'flex' : 'none';
}

/**
 * Load NOAA buoy data for session time range
 */
async function loadBuoyData(startTime, endTime) {
    if (!startTime || !endTime) return;

    try {
        const startTs = new Date(startTime).getTime() / 1000;
        const endTs = new Date(endTime).getTime() / 1000;

        const response = await fetch(
            `${API_BASE}/api/buoys/data?start_ts=${startTs}&end_ts=${endTs}`
        );

        if (!response.ok) {
            console.warn('Failed to fetch buoy data:', response.status);
            return;
        }

        const data = await response.json();
        const buoyData = data.buoys || {};

        // Update map with buoy markers
        if (mapView) {
            mapView.setBuoyData(buoyData);
        }

        // Update chart with buoy time series
        if (chartPanel) {
            chartPanel.setBuoyData(buoyData);
        }

        console.log(`Loaded buoy data for ${Object.keys(buoyData).length} stations`);
    } catch (error) {
        console.error('Error loading buoy data:', error);
    }
}

/**
 * Update session metadata UI fields
 */
function updateSessionMetaUI(sessionData) {
    const metaContainer = document.getElementById('session-meta');
    const nameInput = document.getElementById('session-name');
    const boatSelect = document.getElementById('boat-select');

    if (metaContainer) {
        metaContainer.style.display = 'flex';
    }

    if (nameInput) {
        nameInput.value = sessionData.name || '';
    }

    if (boatSelect) {
        boatSelect.value = sessionData.boat || '';
    }
}

/**
 * Save session metadata (name, boat)
 */
async function saveSessionMeta() {
    if (!currentDeviceId || !currentSessionDate) {
        console.error('No session loaded');
        return;
    }

    const nameInput = document.getElementById('session-name');
    const boatSelect = document.getElementById('boat-select');
    const btnSave = document.getElementById('btn-save-meta');

    const name = nameInput?.value?.trim() || null;
    const boat = boatSelect?.value || null;

    // Disable button while saving
    if (btnSave) {
        btnSave.disabled = true;
        btnSave.textContent = 'Saving...';
    }

    try {
        const response = await fetch(`${API_BASE}/api/sessions/${currentDeviceId}/${currentSessionDate}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, boat })
        });

        if (!response.ok) {
            throw new Error('Failed to save');
        }

        // Visual feedback
        if (btnSave) {
            btnSave.textContent = 'Saved!';
            btnSave.style.background = 'var(--success)';
            setTimeout(() => {
                btnSave.textContent = 'Save';
                btnSave.style.background = '';
            }, 1500);
        }

        console.log('Session metadata saved');
    } catch (err) {
        console.error('Failed to save session metadata:', err);
        alert('Failed to save: ' + err.message);
    } finally {
        if (btnSave) {
            btnSave.disabled = false;
            if (btnSave.textContent === 'Saving...') {
                btnSave.textContent = 'Save';
            }
        }
    }
}

/**
 * Cleanup sessions - delete short sessions or sessions without boat
 */
async function cleanupSessions() {
    const btn = document.getElementById('btn-cleanup');
    const MAX_DURATION_MIN = 15;

    try {
        btn.disabled = true;
        btn.textContent = 'Checking...';

        // Fetch all sessions
        const response = await fetch(`${API_BASE}/api/sessions`);
        if (!response.ok) throw new Error('Failed to fetch sessions');

        const data = await response.json();
        const sessions = data.sessions || [];

        // Find sessions to delete: < 15 min OR no boat assigned
        const toDelete = sessions.filter(s => {
            const durationMin = (s.duration_sec || 0) / 60;
            const shortSession = durationMin < MAX_DURATION_MIN;
            const noBoat = !s.boat && durationMin >= MAX_DURATION_MIN;
            return shortSession || noBoat;
        }).map(s => ({
            ...s,
            durationMin: Math.round((s.duration_sec || 0) / 60),
            reason: (s.duration_sec || 0) / 60 < MAX_DURATION_MIN
                ? `${Math.round((s.duration_sec || 0) / 60)}min < ${MAX_DURATION_MIN}min`
                : 'no boat'
        }));

        if (toDelete.length === 0) {
            alert('No sessions to cleanup.\n\nAll sessions are either:\n• Longer than 15 minutes, AND\n• Have a boat assigned');
            return;
        }

        // Build confirmation message
        const sessionList = toDelete.slice(0, 20).map(s =>
            `• ${s.device_id}/${s.date} (${s.reason})`
        ).join('\n');

        const moreText = toDelete.length > 20 ? `\n... and ${toDelete.length - 20} more` : '';

        const confirmed = confirm(
            `Found ${toDelete.length} sessions to delete:\n\n` +
            `${sessionList}${moreText}\n\n` +
            `Delete these sessions permanently?`
        );

        if (!confirmed) return;

        // Delete each session
        btn.textContent = `Deleting 0/${toDelete.length}...`;
        let deleted = 0;
        let errors = 0;

        for (const session of toDelete) {
            try {
                const delResp = await fetch(
                    `${API_BASE}/api/sessions/${session.device_id}/${session.date}`,
                    { method: 'DELETE' }
                );
                if (delResp.ok) {
                    deleted++;
                } else {
                    errors++;
                }
            } catch {
                errors++;
            }
            btn.textContent = `Deleting ${deleted}/${toDelete.length}...`;
        }

        alert(`Cleanup complete!\n\nDeleted: ${deleted} sessions\nErrors: ${errors}`);

        // Reload sessions list
        await loadSessions(false);

    } catch (err) {
        console.error('Cleanup failed:', err);
        alert('Cleanup failed: ' + err.message);
    } finally {
        btn.disabled = false;
        btn.textContent = '🧹 Cleanup';
    }
}

// Initialize on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}
