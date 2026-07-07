import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useTimeState } from "@/stores/timeController";
import { useWindAt } from "@/hooks/useWindAt";
import { fmtKnots } from "@/utils/format";
import { catmullRomInterval, pointAt, smoothTrackLine, speedColor, speedRange, type Track } from "./raceModel";

export interface MapMark {
  id?: string;
  mark_role: string;
  lat: number;
  lng: number;
  /** preview marks (suggest/auto-start-line before apply) render dashed */
  preview?: boolean;
  /** "leg" marks render as a numbered circle (see `seq`); "maneuver" marks
   * render as a small plain dot in a distinct color. Omit for the default
   * diamond (race marks: start/windward/gate/finish…). */
  kind?: "leg" | "maneuver";
  /** Progressive number shown on "leg" marks (matches the LegsTable `#` column). */
  seq?: number;
}

// Imperative Leaflet (not react-leaflet): tracks + marks are drawn once, and
// only the per-boat position markers move on every cursor tick — kept in refs
// so playback doesn't churn React's tree. No hardcoded geography: the view
// always fits the data; with no data it shows a neutral world view.
export function MapView({
  tracks,
  marks = [],
  className = "sf-race__map",
  wind,
}: {
  tracks: Track[];
  marks?: MapMark[];
  className?: string;
  /** Region to show a wind direction/speed overlay for (e.g. the session's
   * start point + start time) — omit to hide the overlay entirely. */
  wind?: { lat: number; lng: number; at?: string | null };
}) {
  const elRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const markersRef = useRef<Record<string, L.CircleMarker>>({});
  const { cursor } = useTimeState();
  const { data: windAt } = useWindAt(wind?.lat, wind?.lng, wind?.at);

  // One-time map + static layer setup (rebuilt when the data identity changes).
  useEffect(() => {
    if (!elRef.current) return;
    const map = L.map(elRef.current, { zoomControl: false, preferCanvas: true });
    L.control.zoom({ position: "bottomright" }).addTo(map);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "© OpenStreetMap contributors",
      maxZoom: 19,
    }).addTo(map);
    mapRef.current = map;

    const bounds: L.LatLngExpression[] = [];
    for (const tr of tracks) {
      const latlngs = tr.pts.map((p) => [p.lat, p.lon] as [number, number]);
      if (!latlngs.length) continue;
      // The drawn line is lightly smoothed, then curved through a Catmull-Rom
      // interpolation per interval — bounds/markers stay on the raw fixes so
      // the true recorded track/position is never altered, only how the line
      // connecting it looks (still one color per original interval, just
      // drawn as a curve through it instead of a straight chord).
      const smoothed = smoothTrackLine(tr.pts);
      // Colored by speed (per-segment) rather than a single flat track color,
      // so a glance at the line shows where the boat was fast vs. slow.
      const [minSog, maxSog] = speedRange(tr);
      for (let i = 1; i < tr.pts.length; i++) {
        const avgSog = (tr.pts[i - 1].sog + tr.pts[i].sog) / 2;
        const color = speedColor(avgSog, minSog, maxSog);
        const p0 = smoothed[Math.max(0, i - 2)];
        const p1 = smoothed[i - 1];
        const p2 = smoothed[i];
        const p3 = smoothed[Math.min(smoothed.length - 1, i + 1)];
        const curve = catmullRomInterval(p0, p1, p2, p3);
        for (let k = 1; k < curve.length; k++) {
          L.polyline([curve[k - 1], curve[k]], { color, weight: 3, opacity: 0.85 }).addTo(map);
        }
      }
      bounds.push(...latlngs);
      const m = L.circleMarker(latlngs[0], {
        radius: 6,
        color: "#1a1a1a",
        weight: 2,
        fillColor: tr.color,
        fillOpacity: 1,
      });
      m.bindTooltip(tr.name);
      m.addTo(map);
      markersRef.current[tr.id] = m;
    }

    for (const mk of marks) {
      const icon =
        mk.kind === "leg"
          ? L.divIcon({ className: "sf-markicon sf-markicon--leg", html: `${mk.seq ?? ""}`, iconSize: [18, 18] })
          : mk.kind === "maneuver"
            ? L.divIcon({ className: "sf-markicon sf-markicon--maneuver", html: "", iconSize: [10, 10] })
            : L.divIcon({
                className: mk.preview ? "sf-markicon sf-markicon--preview" : "sf-markicon",
                html: "◆",
                iconSize: [16, 16],
              });
      L.marker([mk.lat, mk.lng], { icon }).bindTooltip(mk.mark_role).addTo(map);
      bounds.push([mk.lat, mk.lng]);
    }

    if (bounds.length) map.fitBounds(L.latLngBounds(bounds).pad(0.1));
    else map.setView([20, 0], 2); // neutral world view when there is no data

    return () => {
      map.remove();
      mapRef.current = null;
      markersRef.current = {};
    };
  }, [tracks, marks]);

  // Move position markers to the cursor time.
  useEffect(() => {
    for (const tr of tracks) {
      const marker = markersRef.current[tr.id];
      if (!marker) continue;
      const p = pointAt(tr, cursor);
      if (p) marker.setLatLng([p.lat, p.lon]);
    }
  }, [cursor, tracks]);

  const observation = windAt?.observation;
  return (
    <div className={`${className} sf-map`}>
      <div ref={elRef} className="sf-map__surface" />
      {observation?.twd_deg != null && (
        <div className="sf-map__wind" title={fmtKnots(observation.tws_kts)}>
          <span
            className="sf-map__wind-arrow"
            style={{ transform: `rotate(${observation.twd_deg}deg)` }}
          >
            ↑
          </span>
          <span className="sf-map__wind-speed">{fmtKnots(observation.tws_kts)}</span>
        </div>
      )}
    </div>
  );
}
