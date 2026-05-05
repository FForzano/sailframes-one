// Build a structured "race briefing" JSON document from the dashboard's
// in-memory state. Shipped to the chat Lambda with every turn.
//
// Two design rules the LLM expects:
//
// 1. Every boat's primary label is its team/boat name. Device IDs
//    (E1..E6) are kept under boat_id for round-trip but the system
//    prompt forbids surfacing them.
//
// 2. Every timestamp is a { local, t_sec } pair:
//      local: "11:34:22" in the venue timezone (America/New_York)
//      t_sec: integer seconds from race start
//    The model uses local for human readability and t_sec for the
//    `(t=N)` suffix so the chat UI can linkify it back into a
//    timeline jump.

(function () {
  'use strict';

  const NS = (window.SailFramesBriefing = window.SailFramesBriefing || {});
  const VENUE_TZ = 'America/New_York';

  function fmtLocal(ms) {
    if (ms == null) return null;
    return new Date(ms).toLocaleTimeString('en-US', {
      timeZone: VENUE_TZ,
      hour12: false,
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    });
  }
  function fmtTime(ms, startMs) {
    if (ms == null) return null;
    return {
      local: fmtLocal(ms),
      t_sec: startMs != null ? Math.max(0, Math.round((ms - startMs) / 1000)) : null,
    };
  }
  const round = (x, p = 1) => {
    if (x == null || isNaN(x)) return null;
    const m = Math.pow(10, p);
    return Math.round(x * m) / m;
  };

  function summarizeWind(samples, startMs) {
    if (!samples || !samples.length) return null;
    let sx = 0, sy = 0, twsSum = 0, twsMin = Infinity, twsMax = -Infinity;
    for (const s of samples) {
      const r = (s.twd || 0) * Math.PI / 180;
      sx += Math.sin(r); sy += Math.cos(r);
      twsSum += s.tws || 0;
      if (s.tws != null) {
        if (s.tws < twsMin) twsMin = s.tws;
        if (s.tws > twsMax) twsMax = s.tws;
      }
    }
    const twdAvg = (Math.atan2(sx, sy) * 180 / Math.PI + 360) % 360;
    const twsAvg = twsSum / samples.length;

    const shifts = [];
    let baseline = samples[0].twd;
    let baselineTime = samples[0].tMs;
    for (let i = 1; i < samples.length; i++) {
      const diff = ((samples[i].twd - baseline + 540) % 360) - 180;
      if (Math.abs(diff) >= 10 && samples[i].tMs - baselineTime >= 5 * 60 * 1000) {
        shifts.push({
          at: fmtTime(samples[i].tMs, startMs),
          delta_deg: Math.round(diff),
          direction: diff > 0 ? 'right' : 'left',
        });
        baseline = samples[i].twd;
        baselineTime = samples[i].tMs;
      }
    }
    return {
      twd_avg_deg: Math.round(twdAvg),
      tws_avg_kn: round(twsAvg, 1),
      tws_range_kn: [round(twsMin === Infinity ? null : twsMin, 1),
                     round(twsMax === -Infinity ? null : twsMax, 1)],
      n_samples: samples.length,
      notable_shifts: shifts.slice(0, 5),
    };
  }

  function summarizeBoat(deviceId, boatMeta, layer, legRows, maneuvers, finishOrder, startMs) {
    const myLegs = (legRows || []).filter((r) => r.deviceId === deviceId);
    const myManeuvers = (maneuvers || []).filter((m) => m.deviceId === deviceId);
    const tacks = myManeuvers.filter((m) => m.type === 'tack');
    const gybes = myManeuvers.filter((m) => m.type === 'gybe');

    const avgLoss = (arr) => arr.length
      ? round(arr.reduce((a, b) => a + (b.loss || 0), 0) / arr.length, 2)
      : null;

    const finishIdx = finishOrder ? finishOrder.indexOf(deviceId) : -1;
    const finishMs = layer?.roundingTimes && layer.roundingTimes.length
      ? layer.roundingTimes[layer.roundingTimes.length - 1] : null;

    const totalDistM = myLegs.reduce((a, r) => a + (r.distM || 0), 0);
    const totalTimeSec = myLegs.reduce((a, r) => a + (r.durationSec || 0), 0);

    const meta = boatMeta?.boat || {};
    const team = meta.team_name || meta.boat_name || deviceId;
    const boatName = meta.boat_name || team;

    return {
      name: team,                // primary human label — what the LLM should use
      boat_name: boatName,       // hull/skipper name if distinct from team
      boat_id: deviceId,         // device serial — internal only, never surface
      finish_position: finishIdx >= 0 ? finishIdx + 1 : null,
      finish: finishMs != null ? fmtTime(finishMs, startMs) : null,
      total_time_sec: totalTimeSec ? Math.round(totalTimeSec) : null,
      total_distance_nm: totalDistM ? round(totalDistM / 1852, 2) : null,
      legs_completed: myLegs.length,
      legs: myLegs.map((r) => ({
        leg: r.leg,
        time_sec: round(r.durationSec, 0),
        avg_speed_kn: round(r.avgSog, 2),
        avg_polar_pct: r.avgPolPct == null ? null : round(r.avgPolPct, 0),
        distance_m: round(r.distM, 0),
      })),
      maneuvers: {
        tacks: tacks.length,
        gybes: gybes.length,
        avg_tack_speed_loss_kn: avgLoss(tacks),
        avg_gybe_speed_loss_kn: avgLoss(gybes),
        worst_tack: tacks.length ? (() => {
          const w = tacks.reduce((a, b) => ((b.loss || 0) > (a.loss || 0) ? b : a));
          return { at: fmtTime(w.tStart, startMs), speed_loss_kn: round(w.loss, 2) };
        })() : null,
      },
    };
  }

  /**
   * @param {object} ctx in-memory state from race-app.js (see file header).
   * @returns {object} briefing JSON
   */
  NS.build = function (ctx) {
    const c = ctx.currentRace || {};
    const startMs = c.start_time ? new Date(c.start_time).getTime() : null;
    const endMs   = c.end_time   ? new Date(c.end_time).getTime()   : null;

    const boatsMap = ctx.raceDataBoats || {};
    const layers = ctx.boatLayers || {};
    const boatIds = Object.keys(boatsMap);
    const wind = summarizeWind(ctx.weatherWindSamples || [], startMs);

    return {
      race: {
        id: c.race_id,
        name: c.name,
        date: c.date,
        venue: c.venue || 'Boston Harbor',
        timezone: VENUE_TZ,
        course_type: c.course_type || null,
        course: (c.course || []).map((m) => ({
          name: m.name, type: m.type,
          lat: round(m.lat, 5), lon: round(m.lon, 5),
        })),
        start: startMs != null ? { local: fmtLocal(startMs), t_sec: 0 } : null,
        end:   endMs != null   ? fmtTime(endMs, startMs) : null,
        wind_source: ctx.weatherWindSource || null,
        wind: wind,
      },
      fleet: boatIds.map((id) => {
        const m = boatsMap[id]?.boat || {};
        return m.team_name || m.boat_name || id;
      }),
      boats: boatIds.map((id) => summarizeBoat(
        id, boatsMap[id], layers[id], ctx.legRows, ctx.maneuvers, ctx.finishOrder, startMs
      )),
      generated_at: new Date().toISOString(),
    };
  };
})();
