/**
 * SailFrames Analytics Application
 * Main entry point that coordinates all components
 */

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

    // Load sessions list
    await loadSessions();

    // Setup session selector
    const sessionSelect = document.getElementById('session-select');
    sessionSelect.addEventListener('change', (e) => {
        if (e.target.value) {
            const [deviceId, date] = e.target.value.split('/');
            loadSession(deviceId, date);
        }
    });

    console.log('Initialization complete');
}

/**
 * Load available sessions
 */
async function loadSessions() {
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

        // Add session options
        sessions.forEach(session => {
            const option = document.createElement('option');
            option.value = `${session.device_id}/${session.date}`;

            const duration = session.duration_minutes
                ? ` (${session.duration_minutes} min)`
                : '';
            const video = session.has_video ? ' [VIDEO]' : '';

            option.textContent = `${session.date}${duration}${video}`;
            select.appendChild(option);
        });

        // Auto-select first session if available
        if (sessions.length > 0) {
            select.value = `${sessions[0].device_id}/${sessions[0].date}`;
            loadSession(sessions[0].device_id, sessions[0].date);
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

    try {
        // Load session data
        const response = await fetch(
            `${API_BASE}/api/data/${deviceId}/${date}?sensors=gps,imu,wind,pressure`
        );

        if (!response.ok) throw new Error('Failed to fetch session data');

        const sessionData = await response.json();
        currentSession = sessionData;

        // Extract GPS data for map
        const gpsData = sessionData.data
            .filter(p => p.gps)
            .map(p => ({
                t: p.t,
                lat: p.gps.lat,
                lon: p.gps.lon,
                speed_kn: p.gps.speed_kn,
                course: p.gps.course
            }));

        // Update components
        mapView.setData(gpsData);
        chartPanel.setData(sessionData);

        // Set time controller bounds
        if (sessionData.start_time && sessionData.end_time) {
            window.timeController.setSession(
                sessionData.start_time,
                sessionData.end_time
            );
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

// Initialize on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}
