// Start Review — modal overlay that replays the 3-minute pre-start
// sequence with official RRS Appendix S horn signals.
//
// - Own Leaflet map, zoomed to the start line.
// - Own playback clock from t = -180s to t = +60s (gun at t = 0).
// - Web Audio horn synthesis (no audio assets to host).
// - Skips the optional 3:15 alert per request.
// - AudioContext is created on user gesture (open click), so no autoplay
//   policy violations and no surprise sound until the user hits play.
//
// Public API:
//   SailFramesStartReview.open({ currentRace, raceData, boatLayers,
//                                BOAT_COLORS, apiBase })

(function () {
  'use strict';

  const NS = (window.SailFramesStartReview = window.SailFramesStartReview || {});

  // Pre-start signal schedule. RRS Appendix S 3-minute, optional 3:15
  // alert intentionally omitted. Pattern letters: L = long (~1.5s),
  // S = short (~0.4s), space = small inter-group gap.
  const SIGNALS = [
    { t: -180, pattern: 'L L L', label: '3:00 — three long' },
    { t: -120, pattern: 'L L',   label: '2:00 — two long' },
    { t:  -90, pattern: 'L SSS', label: '1:30 — one long, three short' },
    { t:  -60, pattern: 'L',     label: '1:00 — one long' },
    { t:  -30, pattern: 'SSS',   label: '0:30 — three short' },
    { t:  -20, pattern: 'SS',    label: '0:20 — two short' },
    { t:  -10, pattern: 'S',     label: '0:10 — one short' },
    { t:   -5, pattern: 'S',     label: '0:05' },
    { t:   -4, pattern: 'S',     label: '0:04' },
    { t:   -3, pattern: 'S',     label: '0:03' },
    { t:   -2, pattern: 'S',     label: '0:02' },
    { t:   -1, pattern: 'S',     label: '0:01' },
    { t:    0, pattern: 'L',     label: 'START' },
  ];

  const T_START = -180;
  const T_END   =  60;

  // Internal state — instance-of-one because there's only one panel.
  let rootEl, mapEl, countdownEl, scrubberEl, playBtn, muteCb, signalLabelEl;
  let map, boatMarkers = {};
  let ctx = null;             // dashboard ctx passed to open()
  let preStartData = null;    // padded GPS data fetched on open
  let audio = null;
  let muted = false;

  let t = T_START;            // playback time in seconds (gun = 0)
  let running = false;
  let lastFrameMs = 0;
  let firedSignals = new Set();
  let rafHandle = null;

  // ---------- DOM ----------

  function build() {
    rootEl = document.createElement('div');
    rootEl.className = 'sf-sr-overlay';
    rootEl.hidden = true;
    rootEl.innerHTML = `
      <div class="sf-sr-panel">
        <header class="sf-sr-header">
          <strong class="sf-sr-title">Start Review</strong>
          <span class="sf-sr-race-name"></span>
          <button class="sf-sr-close" aria-label="Close">×</button>
        </header>
        <div class="sf-sr-body">
          <div class="sf-sr-map"></div>
          <div class="sf-sr-countdown">−3:00</div>
          <div class="sf-sr-signal" aria-live="polite"></div>
        </div>
        <footer class="sf-sr-controls">
          <button class="sf-sr-play">▶ Play</button>
          <button class="sf-sr-replay" title="Restart from −3:00">⟲</button>
          <input type="range" class="sf-sr-scrubber"
                 min="${T_START}" max="${T_END}" step="1" value="${T_START}">
          <span class="sf-sr-time">−3:00</span>
          <label class="sf-sr-mute">
            <input type="checkbox"> Mute horns
          </label>
        </footer>
      </div>`;
    document.body.appendChild(rootEl);

    mapEl         = rootEl.querySelector('.sf-sr-map');
    countdownEl   = rootEl.querySelector('.sf-sr-countdown');
    signalLabelEl = rootEl.querySelector('.sf-sr-signal');
    scrubberEl    = rootEl.querySelector('.sf-sr-scrubber');
    playBtn       = rootEl.querySelector('.sf-sr-play');
    muteCb        = rootEl.querySelector('.sf-sr-mute input');

    rootEl.querySelector('.sf-sr-close').onclick  = NS.close;
    rootEl.querySelector('.sf-sr-replay').onclick = () => seek(T_START);
    playBtn.onclick = togglePlay;
    scrubberEl.addEventListener('input', () => seek(parseInt(scrubberEl.value, 10) || 0));
    muteCb.addEventListener('change', () => { muted = muteCb.checked; });

    // Esc to close
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && !rootEl.hidden) NS.close();
    });
  }

  // ---------- Audio ----------

  function ensureAudio() {
    if (audio) return audio;
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return null;
    audio = new AC();
    return audio;
  }

  function horn(whenSec, durSec, freq = 220) {
    if (!audio || muted) return;
    const start = audio.currentTime + Math.max(0, whenSec);
    const osc = audio.createOscillator();
    const filt = audio.createBiquadFilter();
    const gain = audio.createGain();
    osc.type = 'sawtooth';
    osc.frequency.value = freq;
    filt.type = 'lowpass';
    filt.frequency.value = 900;
    filt.Q.value = 0.7;
    gain.gain.setValueAtTime(0.0001, start);
    gain.gain.exponentialRampToValueAtTime(0.45, start + 0.04);
    gain.gain.setValueAtTime(0.45, start + Math.max(0.05, durSec - 0.06));
    gain.gain.exponentialRampToValueAtTime(0.0001, start + durSec);
    osc.connect(filt).connect(gain).connect(audio.destination);
    osc.start(start);
    osc.stop(start + durSec + 0.05);
  }

  function playPattern(pattern) {
    let offset = 0;
    for (const ch of pattern) {
      if (ch === 'L')      { horn(offset, 1.5); offset += 1.7; }
      else if (ch === 'S') { horn(offset, 0.4); offset += 0.6; }
      else if (ch === ' ') { offset += 0.3; }
    }
  }

  // ---------- Map / boats ----------

  function ensureMap() {
    if (map) return;
    map = L.map(mapEl, {
      attributionControl: false,
      zoomControl: true,
    });
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 20,
    }).addTo(map);
  }

  function frameStartLine(race) {
    const sl = race?.start_line;
    if (sl && sl.pin_lat != null && sl.boat_lat != null) {
      const bounds = L.latLngBounds(
        [sl.pin_lat, sl.pin_lon],
        [sl.boat_lat, sl.boat_lon]
      );
      // Generous padding so boats positioning around the line are visible.
      map.fitBounds(bounds.pad(2.5), { animate: false });
      // Draw the line itself in cyan, matching the dashboard.
      L.polyline(
        [[sl.pin_lat, sl.pin_lon], [sl.boat_lat, sl.boat_lon]],
        { color: '#22d3ee', weight: 3, opacity: 0.9 }
      ).addTo(map);
      L.circleMarker([sl.pin_lat,  sl.pin_lon],  { radius: 6, color: '#22d3ee', fillOpacity: 1 }).addTo(map).bindTooltip('Pin');
      L.circleMarker([sl.boat_lat, sl.boat_lon], { radius: 6, color: '#22d3ee', fillOpacity: 1 }).addTo(map).bindTooltip('Committee');
    } else {
      // Fallback: fit course bounds.
      const marks = (race?.course || []).filter((m) => m.lat != null);
      if (marks.length) {
        const b = L.latLngBounds(marks.map((m) => [m.lat, m.lon]));
        map.fitBounds(b.pad(0.5), { animate: false });
      } else {
        map.setView([42.34, -70.95], 13);
      }
    }
    setTimeout(() => map.invalidateSize(), 50);
  }

  function rebuildBoatMarkers() {
    for (const m of Object.values(boatMarkers)) m.remove();
    boatMarkers = {};
    if (!preStartData?.boats) return;
    for (const [deviceId, info] of Object.entries(preStartData.boats)) {
      const meta = info.boat || {};
      const color = (ctx.BOAT_COLORS && ctx.BOAT_COLORS[deviceId]) || '#1f2d3d';
      const label = meta.team_name || meta.boat_name || deviceId;
      const marker = L.circleMarker([0, 0], {
        radius: 7, color, fillColor: color, fillOpacity: 0.9, weight: 2,
      }).bindTooltip(label, { direction: 'right', offset: [10, 0] });
      // Pre-parse timestamps once for fast lookup during animation.
      const gps = (info.sensors?.gps || []).map((p) => ({
        ms: new Date(p.t).getTime(),
        lat: p.lat, lon: p.lon,
        speed: p.speed_kn, course: p.course,
      })).filter((p) => Number.isFinite(p.ms) && p.lat && p.lon);
      gps.sort((a, b) => a.ms - b.ms);
      boatMarkers[deviceId] = { marker, gps, raceStartMs: 0 };
    }
  }

  function positionAt(track, absMs) {
    const a = track.gps;
    if (!a.length) return null;
    if (absMs < a[0].ms) return null;
    if (absMs > a[a.length - 1].ms) return a[a.length - 1];
    let lo = 0, hi = a.length - 1;
    while (lo < hi - 1) {
      const mid = (lo + hi) >> 1;
      if (a[mid].ms <= absMs) lo = mid; else hi = mid;
    }
    const f = (absMs - a[lo].ms) / Math.max(1, a[hi].ms - a[lo].ms);
    return {
      lat: a[lo].lat + (a[hi].lat - a[lo].lat) * f,
      lon: a[lo].lon + (a[hi].lon - a[lo].lon) * f,
    };
  }

  function renderBoats() {
    const startMs = ctx.currentRace?.start_time ? new Date(ctx.currentRace.start_time).getTime() : null;
    if (!startMs) return;
    const absMs = startMs + t * 1000;
    for (const [id, track] of Object.entries(boatMarkers)) {
      const p = positionAt(track, absMs);
      if (!p) {
        track.marker.remove();
      } else {
        track.marker.setLatLng([p.lat, p.lon]);
        if (!track.marker._map) track.marker.addTo(map);
      }
    }
  }

  // ---------- Time + signals ----------

  function fmtCountdown(secs) {
    const n = Math.round(secs);
    if (n <= 0) {
      if (n === 0) return 'GUN';
      const a = -n;
      return `−${Math.floor(a / 60)}:${String(a % 60).padStart(2, '0')}`;
    }
    return `+${Math.floor(n / 60)}:${String(n % 60).padStart(2, '0')}`;
  }

  function updateCountdown() {
    countdownEl.textContent = fmtCountdown(t);
    countdownEl.classList.toggle('sf-sr-cd-final', t >= -10 && t < 0);
    countdownEl.classList.toggle('sf-sr-cd-gun', Math.abs(t) < 0.5);
    scrubberEl.value = String(Math.round(t));
    rootEl.querySelector('.sf-sr-time').textContent = fmtCountdown(t);
  }

  function maybeFireSignals(prevT, currT) {
    // Fire any signal whose t crossed during this tick. Direction-aware:
    // only fire when moving forward (so scrub-back doesn't double-fire).
    if (currT < prevT) return;
    for (let i = 0; i < SIGNALS.length; i++) {
      const s = SIGNALS[i];
      if (firedSignals.has(i)) continue;
      if (s.t > prevT && s.t <= currT) {
        firedSignals.add(i);
        signalLabelEl.textContent = s.label;
        playPattern(s.pattern);
      }
    }
  }

  // ---------- Playback loop ----------

  function loop(now) {
    rafHandle = null;
    if (!running) return;
    const dt = lastFrameMs ? (now - lastFrameMs) / 1000 : 0;
    lastFrameMs = now;
    const prev = t;
    t += dt;
    if (t >= T_END) {
      t = T_END;
      stop();
      updateCountdown();
      renderBoats();
      return;
    }
    maybeFireSignals(prev, t);
    updateCountdown();
    renderBoats();
    rafHandle = requestAnimationFrame(loop);
  }

  function start() {
    if (running) return;
    running = true;
    lastFrameMs = 0;
    playBtn.textContent = '⏸ Pause';
    if (audio?.state === 'suspended') audio.resume();
    rafHandle = requestAnimationFrame(loop);
  }
  function stop() {
    running = false;
    playBtn.textContent = '▶ Play';
    if (rafHandle) cancelAnimationFrame(rafHandle);
    rafHandle = null;
  }
  function togglePlay() {
    if (running) stop(); else start();
  }
  function seek(newT) {
    const clamped = Math.max(T_START, Math.min(T_END, newT));
    if (clamped < t) firedSignals.clear();
    t = clamped;
    lastFrameMs = 0;
    updateCountdown();
    renderBoats();
  }

  // ---------- Open / close ----------

  async function fetchPaddedRaceData(raceId) {
    const apiBase = ctx.apiBase || window.location.origin;
    const url = `${apiBase}/api/races/${raceId}/data?sensors=gps&pad_start=240&pad_end=120`;
    try {
      const r = await fetch(url);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return await r.json();
    } catch (e) {
      console.warn('[StartReview] padded data fetch failed, using race window only:', e);
      // Fallback: rebuild the same shape from boatLayers.
      const boats = {};
      for (const id of Object.keys(ctx.boatLayers || {})) {
        const layer = ctx.boatLayers[id];
        boats[id] = {
          boat: ctx.raceData?.boats?.[id]?.boat || {},
          sensors: { gps: layer?.data || [] },
        };
      }
      return { boats };
    }
  }

  NS.open = async function (incomingCtx) {
    if (!rootEl) build();
    ctx = incomingCtx || {};
    const r = ctx.currentRace;
    if (!r || !r.start_time) {
      alert('This race has no start time set — cannot run start review.');
      return;
    }
    rootEl.querySelector('.sf-sr-race-name').textContent = ` — ${r.name || ''}`;
    rootEl.hidden = false;

    ensureAudio();        // user gesture: the click that triggered open()
    ensureMap();
    frameStartLine(r);

    // Reset playback
    t = T_START;
    firedSignals.clear();
    signalLabelEl.textContent = '';
    updateCountdown();
    stop();

    preStartData = await fetchPaddedRaceData(r.race_id);
    rebuildBoatMarkers();
    renderBoats();
  };

  NS.close = function () {
    if (!rootEl) return;
    stop();
    rootEl.hidden = true;
    if (audio) audio.suspend();
  };
})();
