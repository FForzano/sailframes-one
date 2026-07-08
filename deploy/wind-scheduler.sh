#!/bin/sh
# Periodic wind-fetch scheduler for the self-hosted stack.
#
# Loops forever with minute granularity; for each provider whose configured
# interval has elapsed, POSTs /api/system/wind/fetch (hook-token auth). The
# backend iterates that provider's wind_stations and upserts observations —
# the unique (station, observed_at) key makes re-runs idempotent, so an
# occasional double fire is harmless.
#
# Also periodically POSTs /api/system/wind/reconcile: Open-Meteo forecast
# readings are provisional, so once its archive/reanalysis has had time to
# catch up, this overwrites the cached rows with the settled values (see
# services/wind_lookup.reconcile_forecasts). Independent of the fetch cadence
# above — reconciliation only ever touches open_meteo stations.
#
# Cadence env (minutes), one per provider:
#   WIND_FETCH_INTERVAL_MIN_NOAA_NDBC        (default 30)
#   WIND_RECONCILE_INTERVAL_MIN_OPEN_METEO   (default 1440, i.e. once a day)
set -eu

BACKEND_URL="${BACKEND_URL:-http://backend:8000}"
TOKEN="${SAILFRAMES_HOOK_TOKEN:?SAILFRAMES_HOOK_TOKEN is required}"

NDBC_INTERVAL_MIN="${WIND_FETCH_INTERVAL_MIN_NOAA_NDBC:-30}"
RECONCILE_INTERVAL_MIN="${WIND_RECONCILE_INTERVAL_MIN_OPEN_METEO:-1440}"
ndbc_last=0
reconcile_last=0

fetch() {
    provider="$1"
    echo "[wind-scheduler] fetching provider=$provider"
    curl -fsS -X POST \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d "{\"provider\":\"$provider\"}" \
        "$BACKEND_URL/api/system/wind/fetch" \
        || echo "[wind-scheduler] fetch failed for $provider (will retry next cycle)"
    echo ""
}

reconcile() {
    echo "[wind-scheduler] reconciling open_meteo forecasts"
    curl -fsS -X POST \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        "$BACKEND_URL/api/system/wind/reconcile" \
        || echo "[wind-scheduler] reconcile failed (will retry next cycle)"
    echo ""
}

echo "[wind-scheduler] started (noaa_ndbc every ${NDBC_INTERVAL_MIN}m, open_meteo reconcile every ${RECONCILE_INTERVAL_MIN}m)"
while true; do
    now=$(date +%s)
    if [ $((now - ndbc_last)) -ge $((NDBC_INTERVAL_MIN * 60)) ]; then
        fetch "noaa_ndbc"
        ndbc_last=$now
    fi
    if [ $((now - reconcile_last)) -ge $((RECONCILE_INTERVAL_MIN * 60)) ]; then
        reconcile
        reconcile_last=$now
    fi
    sleep 60
done
