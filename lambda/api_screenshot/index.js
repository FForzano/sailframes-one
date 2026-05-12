// SailFrames screenshot Lambda. Server-side headless Chromium navigates
// to the live race page, waits for it to be fully ready (race data
// loaded, Leaflet map sized, tiles loaded), seeks to a specific moment +
// fits the view to a section's time range, then screenshots the
// `#race-map` element. Returns a PNG dataURL.
//
// This is the architecturally correct path for capturing the actual
// Light Blue basemap (Carto dark + CSS invert/hue-rotate filter) — real
// browser, real CSS, real Leaflet rendering. None of the in-browser
// html2canvas hacks needed.
//
// Invoked by the coach Python Lambda (via boto3 lambda.invoke), so this
// function itself doesn't need auth — only the coach Lambda role can
// call it.
//
// Event payload (JSON body):
//   {
//     "race_id":          "abc-123",        // required
//     "t_seconds":        420,              // optional: playback cursor (s from race start)
//     "t_start_seconds":  300,              // optional: window start for fit-to-bounds
//     "t_end_seconds":    600,              // optional: window end   for fit-to-bounds
//     "w":                1100,             // optional: viewport width
//     "h":                720               // optional: viewport height
//   }
//
// Returns:
//   { "image_data_uri": "data:image/png;base64,..." }

const chromium = require('@sparticuz/chromium');
const puppeteer = require('puppeteer-core');

const SITE_BASE = process.env.SITE_BASE || 'https://sailframes.com';

// Browser caching across warm invocations: Lambda containers can be reused
// for ~5-10 minutes. Reusing the browser saves ~3 s of Chrome startup per
// capture. We keep a process-level singleton.
let browserPromise = null;

async function getBrowser() {
    if (browserPromise) {
        try {
            const b = await browserPromise;
            if (b && b.process() && !b.process().killed) return b;
        } catch (_) { /* fall through and re-launch */ }
    }
    browserPromise = puppeteer.launch({
        args: chromium.args,
        defaultViewport: chromium.defaultViewport,
        executablePath: await chromium.executablePath(),
        headless: chromium.headless,
        ignoreHTTPSErrors: true,
    });
    return browserPromise;
}

function jsonResp(statusCode, payload) {
    return {
        statusCode,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    };
}

exports.handler = async (event, context) => {
    let body;
    try {
        body = (typeof event.body === 'string') ? JSON.parse(event.body) : (event.body || event);
    } catch (e) {
        return jsonResp(400, { error: 'invalid JSON body', detail: e.message });
    }

    const {
        race_id,
        t_seconds,
        t_start_seconds,
        t_end_seconds,
        // Square viewport so race-shaped (vertical windward-leeward)
        // course content fills the canvas instead of being squashed
        // into a wide rectangle with empty horizontal sides.
        w = 900,
        h = 900,
    } = body;

    if (!race_id) return jsonResp(400, { error: 'race_id required' });

    const url = `${SITE_BASE}/race.html?race=${encodeURIComponent(race_id)}` +
                `&leaderboard_hidden=1&legend_compact=1`;

    let page;
    let browser;
    try {
        browser = await getBrowser();
        page = await browser.newPage();
        await page.setViewport({ width: w, height: h, deviceScaleFactor: 1 });

        // Helpful console pipe so issues show up in CloudWatch.
        page.on('console', msg => console.log('[page]', msg.type(), msg.text().slice(0, 200)));
        page.on('pageerror', err => console.log('[pageerror]', err.message));

        await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 45000 });

        // Wait for the race page to report it's fully ready (race data
        // loaded, Leaflet map sized, ≥1 boat layer placed). 60 s — race
        // data can take 10-20 s to fetch + parse for a 6-boat race.
        await page.waitForFunction(
            () => typeof window.captureReady === 'function' && window.captureReady(),
            { timeout: 60000, polling: 500 }
        );

        // Extra settle time after captureReady — race-app.js may still
        // be running per-frame work (boat positioning, leaderboard, etc).
        await new Promise((r) => setTimeout(r, 500));

        // Move the playback cursor (so trails reflect the moment we want).
        if (typeof t_seconds === 'number' && t_seconds > 0) {
            await page.evaluate((t) => { if (window.seekTo) window.seekTo(t); }, t_seconds);
            // Let Leaflet apply the seek + redraw boats / trails / labels.
            await new Promise((r) => setTimeout(r, 600));
        }

        // Frame the section's bounds (boat positions during the window).
        if (typeof t_start_seconds === 'number' && typeof t_end_seconds === 'number') {
            await page.evaluate((s, e) => {
                if (window.fitToTimeRange) window.fitToTimeRange(s, e);
            }, t_start_seconds, t_end_seconds);
            await new Promise((r) => setTimeout(r, 400));
        }

        // Wait for the new viewport's tiles to load fully.
        try {
            await page.waitForFunction(
                () => {
                    const tiles  = document.querySelectorAll('.leaflet-tile-pane img.leaflet-tile');
                    const loaded = document.querySelectorAll('.leaflet-tile-pane img.leaflet-tile-loaded');
                    return tiles.length > 0 && tiles.length === loaded.length;
                },
                { timeout: 12000 }
            );
        } catch (_) { /* continue with whatever loaded */ }
        await new Promise((r) => setTimeout(r, 600));

        // Hide the controls we don't want in the screenshot.
        await page.evaluate(() => {
            const sels = [
                '.marker-overlays-control',
                '.leaflet-control-layers',
                '.leaflet-control-zoom',
                '.leaflet-control-attribution',
            ];
            for (const sel of sels) {
                for (const node of document.querySelectorAll(sel)) {
                    node.style.display = 'none';
                }
            }
        });

        // Compute screen-space bounding box of all boat positions in the
        // time window — we'll clip the screenshot to that rectangle so
        // empty area outside the action gets cropped away.
        let clip = null;
        if (typeof t_start_seconds === 'number' && typeof t_end_seconds === 'number') {
            clip = await page.evaluate((tStart, tEnd) => {
                if (!window.map || !window.boatLayers || !window.currentRace) return null;
                const raceStart = new Date(window.currentRace.start_time).getTime();
                const tStartMs = raceStart + tStart * 1000;
                const tEndMs = raceStart + tEnd * 1000;
                const xs = [], ys = [];
                for (const layer of Object.values(window.boatLayers)) {
                    if (!Array.isArray(layer.data)) continue;
                    for (const p of layer.data) {
                        if (!p.t || p.lat == null || p.lon == null) continue;
                        const t = new Date(p.t).getTime();
                        if (t < tStartMs || t > tEndMs) continue;
                        const sp = window.map.latLngToContainerPoint([p.lat, p.lon]);
                        xs.push(sp.x); ys.push(sp.y);
                    }
                }
                if (xs.length < 2) return null;
                const mapEl = document.getElementById('race-map');
                const rect = mapEl.getBoundingClientRect();
                const PAD = 50;
                const minX = Math.max(0, Math.min(...xs) - PAD);
                const maxX = Math.min(rect.width, Math.max(...xs) + PAD);
                const minY = Math.max(0, Math.min(...ys) - PAD);
                const maxY = Math.min(rect.height, Math.max(...ys) + PAD);
                return {
                    x: Math.floor(rect.left + minX),
                    y: Math.floor(rect.top + minY),
                    width: Math.ceil(maxX - minX),
                    height: Math.ceil(maxY - minY),
                };
            }, t_start_seconds, t_end_seconds);
        }

        let png;
        if (clip && clip.width > 100 && clip.height > 100) {
            png = await page.screenshot({ type: 'png', encoding: 'base64', clip });
        } else {
            const mapEl = await page.$('#race-map');
            if (!mapEl) throw new Error('#race-map not found');
            png = await mapEl.screenshot({ type: 'png', encoding: 'base64' });
        }

        return jsonResp(200, { image_data_uri: 'data:image/png;base64,' + png });
    } catch (e) {
        console.error('[screenshot] error:', e);
        return jsonResp(500, { error: 'capture_failed', detail: e.message || String(e) });
    } finally {
        if (page) {
            try { await page.close(); } catch (_) {}
        }
    }
};
