// Build a structured "race briefing" JSON document from the dashboard's
// in-memory state. Shipped to the chat Lambda with every turn.
//
// Designed to be small (~5–20 KB): the LLM gets per-boat per-leg
// totals and notable events, NOT raw timeseries. If a question needs
// finer detail than the briefing answers, that's the trigger to add
// drill-down tools (Phase 2).
//
// Consumes the actual race-app.js data shapes:
//   ctx.currentRace          { race_id, name, date, course, start_time, end_time }
//   ctx.raceDataBoats        raceData.boats — { [deviceId]: { boat: {team_name,boat_name,...} } }
//   ctx.boatLayers           { [deviceId]: { data, roundingTimes, times } }
//   ctx.legRows              from computeLegSummary() — { deviceId,team,leg,durationSec,avgSog,avgPolPct,distM }
//   ctx.maneuvers            list — { deviceId,team, tStart,tEnd,durationSec,speedBefore,speedAfter,loss,type }
//   ctx.weatherWindSamples   [{ tMs, twd, tws }]
//   ctx.weatherWindSource    string
//   ctx.finishOrder          [deviceId, ...] in finish order (best first); may be partial

(function () {
  'use strict';

  const NS = (window.SailFramesBriefing = window.SailFramesBriefing || {});

  const fmtIso = (ms) => (ms == null ? null : new Date(ms).toISOString());
  const round = (x, p = 1) => {
    if (x == null || isNaN(x)) return null;
    const m = Math.pow(10, p);
    return Math.round(x * m) / m;
  };

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

    // Largest sustained shift (>= 10° change held for >= 5 min).
    const shifts = [];
    let baseline = samples[0].twd;
    let baselineTime = samples[0].tMs;
    for (let i = 1; i < samples.length; i++) {
      const diff = ((samples[i].twd - baseline + 540) % 360) - 180;
      if (Math.abs(diff) >= 10 && samples[i].tMs - baselineTime >= 5 * 60 * 1000) {
        shifts.push({
          at: fmtIso(samples[i].tMs),
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

  function summarizeBoat(deviceId, boatMeta, layer, legRows, maneuvers, finishOrder) {
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

    const totalLegs = myLegs.length;
    const totalDistM = myLegs.reduce((a, r) => a + (r.distM || 0), 0);
    const totalTimeSec = myLegs.reduce((a, r) => a + (r.durationSec || 0), 0);

    const team = boatMeta?.boat?.team_name || boatMeta?.boat?.boat_name || deviceId;

    return {
      boat_id: deviceId,
      team,
      finish_position: finishIdx >= 0 ? finishIdx + 1 : null,
      finish_time: fmtIso(finishMs),
      total_time_sec: totalTimeSec || null,
      total_distance_nm: totalDistM ? round(totalDistM / 1852, 2) : null,
      legs_completed: totalLegs,
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
          return { at: fmtIso(w.tStart), speed_loss_kn: round(w.loss, 2) };
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
    const boatsMap = ctx.raceDataBoats || {};
    const layers = ctx.boatLayers || {};
    const boatIds = Object.keys(boatsMap);
    const wind = summarizeWind(ctx.weatherWindSamples || []);
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
        wind_source: ctx.weatherWindSource || null,
        wind: wind,
      },
      fleet: boatIds,
      boats: boatIds.map((id) => summarizeBoat(
        id, boatsMap[id], layers[id], ctx.legRows, ctx.maneuvers, ctx.finishOrder
      )),
      generated_at: new Date().toISOString(),
    };
  };
})();
