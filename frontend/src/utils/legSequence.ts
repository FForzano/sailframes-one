import type { SessionLeg, UUID } from "@/types";

/** Progressive number per leg in chronological order (`start_time` ascending)
 * — shared by the LegsTable `#` column and the map's numbered leg markers so
 * the same leg carries the same number in both places. */
export function legSequence(legs: SessionLeg[]): Map<UUID, number> {
  const ordered = legs.slice().sort((a, b) => a.start_time - b.start_time);
  return new Map(ordered.map((l, i) => [l.id, i + 1]));
}
