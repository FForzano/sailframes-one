// Build a structured "race briefing" JSON document from the dashboard's
// in-memory state (currentRace, boats, leg summary, maneuvers, NOAA
// wind samples). Shipped to the chat Lambda with every turn.
//
// Designed to be small (~5–20 KB): the LLM gets per-boat per-leg
// totals and notable events, NOT raw timeseries. If a question needs
// finer detail than the briefing answers, that's the trigger to add
// drill-down tools (Phase 2).
//
// Depends on globals already living in race-app.js:
//   currentRace, boatTracks (or equivalent), raceAvgTWD,
//   weatherWindSamples, weatherWindSource, computeLegSummary(),
//   detectManeuvers() (or pre-computed maneuver list).
//
// This file exposes a single function on window:
//   window.SailFramesBriefing.build({ currentRace, boats, ... }) → object

(function () {
  'use strict';

  const NS = (window.SailFramesBriefing = window.SailFramesBriefing || {});

  function fmtIso(ms) {
    if (ms == null) return null;
    return new Date(ms).toISOString();
  }

  function round(x, p = 1) {
    if (x == null || isNaN(x)) return null;
    const m = Math.pow(10, p);
    return Math.round(x * m) / m;
  }

  // Reduce a TWD/TWS sample series to a compact summary + a few notable shifts.
  function summarizeWind(samples) {
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

    // Find the largest sustained shift (>= 10° change held for >= 5 min).
    const shifts = [];
    let baseline = samples[0].twd;
    let baselineTime = samples[0].t;
    for (let i = 1; i < samples.length; i++) {
      const diff = ((samples[i].twd - baseline + 540) % 360) - 180;
      if (Math.abs(diff) >= 10 && samples[i].t - baselineTime >= 5 * 60 * 1000) {
        shifts.push({
          at: fmtIso(samples[i].t),
          delta_deg: Math.round(diff),
          direction: diff > 0 ? 'right' : 'left',
        });
        baseline = samples[i].twd;
        baselineTime = samples[i].t;
      }
    }
    return {
      twd_avg_deg: Math.round(twdAvg),
      tws_avg_kn: round(twsAvg, 1),
      tws_range_kn: [round(twsMin, 1), round(twsMax, 1)],
      n_samples: samples.length,
      notable_shifts: shifts.slice(0, 5),
    };
  }

  // Per-boat summary derived from leg summary + maneuvers. Keeps the
  // numbers a coach actually cites: leg-by-leg time, %polar, tack/gybe
  // counts, biggest single speed loss event.
  function summarizeBoat(boatId, boatMeta, legRows, maneuvers, finishOrder) {
    const myLegs = legRows.filter((r) => r.deviceId === boatId);
    const myManeuvers = maneuvers.filter((m) => m.deviceId === boatId);

    const tacks = myManeuvers.filter((m) => m.type === 'tack');
    const gybes = myManeuvers.filter((m) => m.type === 'gybe');
    const avgLoss = (arr) => arr.length
      ? round(arr.reduce((a, b) => a + (b.speedLossKn || 0), 0) / arr.length, 2)
      : null;

    return {
      boat_id: boatId,
      hull: boatMeta?.hull || boatMeta?.name || boatId,
      finish_position: finishOrder?.indexOf(boatId) >= 0
        ? finishOrder.indexOf(boatId) + 1 : null,
      finish_time: fmtIso(boatMeta?.finishTimeMs),
      total_time_sec: boatMeta?.totalTimeSec ?? null,
      legs: myLegs.map((r) => ({
        leg: r.leg,
        type: r.legType,        // 'beat'|'reach'|'run'
        time_sec: r.elapsedSec,
        avg_speed_kn: round(r.avgSpeedKn, 2),
        avg_polar_pct: round(r.avgPolarPct, 0),
        distance_sailed_nm: round(r.distSailedNm, 2),
        distance_rhumb_nm: round(r.distRhumbNm, 2),
      })),
      maneuvers: {
        tacks: tacks.length,
        gybes: gybes.length,
        avg_tack_speed_loss_kn: avgLoss(tacks),
        avg_gybe_speed_loss_kn: avgLoss(gybes),
        worst_tack: tacks.length ? {
          at: fmtIso(tacks.reduce((a, b) => (b.speedLossKn > a.speedLossKn ? b : a)).startMs),
          speed_loss_kn: round(Math.max(...tacks.map((t) => t.speedLossKn)), 2),
        } : null,
      },
    };
  }

  /**
   * @param {object} ctx  in-memory state from race-app.js
   *   ctx.currentRace      object with start_time, end_time, course, etc.
   *   ctx.boats            map { deviceId: { hull, finishTimeMs, ... } }
   *   ctx.legRows          rows from computeLegSummary()
   *   ctx.maneuvers        list from detectManeuvers()
   *   ctx.windSamples      [{ t (ms), twd, tws }, ...]
   *   ctx.windSource       e.g. "CSIM3"
   *   ctx.finishOrder      array of deviceIds in finish order
   * @returns {object} briefing JSON
   */
  NS.build = function (ctx) {
    const c = ctx.currentRace || {};
    const boatIds = Object.keys(ctx.boats || {});
    const wind = summarizeWind(ctx.windSamples || []);
    return {
      race: {
        id: c.race_id,
        name: c.name,
        date: c.date,
        venue: c.venue || 'Boston Harbor',
        course_type: c.course_type || null,
        course: (c.course || []).map((m) => ({
          name: m.name, type: m.type,
          lat: round(m.lat, 5), lon: round(m.lon, 5),
        })),
        start_time: c.start_time,
        end_time: c.end_time,
        wind_source: ctx.windSource || null,
        wind: wind,
      },
      fleet: boatIds,
      boats: boatIds.map((id) => summarizeBoat(
        id, ctx.boats[id], ctx.legRows || [], ctx.maneuvers || [], ctx.finishOrder
      )),
      // Optional events list — populated by race-app.js if available.
      notable_events: ctx.notableEvents || [],
      generated_at: new Date().toISOString(),
    };
  };
})();
