import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useTimeState } from "@/stores/timeController";
import { pointAt, type BoatTrack } from "./raceModel";
import type { RaceMark } from "@/types/racedata";

// Imperative Leaflet (not react-leaflet): tracks + marks are drawn once, and
// only the per-boat position markers move on every cursor tick — kept in refs
// so playback doesn't churn React's tree.
export function MapView({ tracks, marks }: { tracks: BoatTrack[]; marks: RaceMark[] }) {
  const elRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const markersRef = useRef<Record<string, L.CircleMarker>>({});
  const { cursor } = useTimeState();

  // One-time map + static layer setup.
  useEffect(() => {
    if (!elRef.current || mapRef.current) return;
    const map = L.map(elRef.current, { zoomControl: true });
    L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
      attribution: "© OpenStreetMap © CARTO",
      maxZoom: 20,
    }).addTo(map);
    mapRef.current = map;

    const bounds: L.LatLngExpression[] = [];
    for (const tr of tracks) {
      const latlngs = tr.pts.map((p) => [p.lat, p.lon] as [number, number]);
      if (latlngs.length) {
        L.polyline(latlngs, { color: tr.color, weight: 2, opacity: 0.8 }).addTo(map);
        bounds.push(...latlngs);
      }
      const m = L.circleMarker([tr.pts[0]?.lat ?? 0, tr.pts[0]?.lon ?? 0], {
        radius: 6,
        color: "#fff",
        weight: 2,
        fillColor: tr.color,
        fillOpacity: 1,
      });
      m.bindTooltip(tr.name, { permanent: false });
      m.addTo(map);
      markersRef.current[tr.id] = m;
    }

    for (const mk of marks) {
      L.marker([mk.lat, mk.lon], {
        icon: L.divIcon({ className: "sf-markicon", html: "◆", iconSize: [16, 16] }),
      })
        .bindTooltip(mk.name || mk.mark_type || "mark", { permanent: false })
        .addTo(map);
      bounds.push([mk.lat, mk.lon]);
    }

    if (bounds.length) map.fitBounds(L.latLngBounds(bounds).pad(0.1));
    else map.setView([42.35, -70.99], 13); // Boston Harbor fallback

    return () => {
      map.remove();
      mapRef.current = null;
      markersRef.current = {};
    };
    // Rebuild only when the track set identity changes.
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

  return <div ref={elRef} className="sf-map" />;
}
