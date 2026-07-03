# Device Protocol

Specifica del protocollo che un device hardware (E1, B, o qualunque device
custom futuro) deve implementare per registrarsi e inviare dati alla
piattaforma. Riferimenti: `er-project.md` (schema dati) e `api-project.md`
(endpoint ad alto livello). Questo file è il dettaglio pensato per chi
scrive firmware.

---

## 1. Identità del device

Ogni device è identificato da un `external_id` univoco e stabile nel tempo
— seriale hardware, UUID BLE, o MAC address, a seconda di cosa il
`device_type` espone in modo affidabile. **Non deve cambiare tra un boot e
l'altro**: è la chiave con cui il server riconosce il device nel claim e in
tutte le richieste successive.

Il device deve conoscere anche il proprio `device_type_id` (o un nome
mappabile server-side, es. `"SailFrames E1"`), comunicato all'atto del
claim.

---

## 2. Provisioning (claim flow)

Un device **non può inviare dati prima di essere reclamato** — non esiste
percorso di auto-registrazione al primo upload (vedi `api-project.md`,
sezione "Registrazione device e ingestion dati").

Sequenza:

1. Un utente, dall'app, avvia il claim: `POST /api/devices/claims` con
   `{device_type_id, nickname?, claim_target}`. Il server risponde con
   `{claim_code, expires_at}` (finestra tipica: 15 minuti).
2. L'utente comunica il `claim_code` al device fuori banda — per l'E1,
   scrivendolo in `config.txt` su SD (`claim_code=XXXXXX`) prima del boot,
   o via comando seriale (`claim <codice>`) se il device è già acceso e in
   modalità provisioning.
3. Il device chiama **una sola volta**, appena ha un `claim_code` in
   config e connettività:

   ```
   POST /api/devices/claim/confirm
   Content-Type: application/json

   { "external_id": "AA:BB:CC:DD:EE:FF", "claim_code": "482913" }
   ```

   Risposta 200:

   ```
   { "device_id": 1234, "device_api_key": "sk_live_...", "issued_at": "2026-07-03T10:00:00Z" }
   ```

4. Il device **deve persistere `device_api_key` su storage non volatile**
   (SD/NVS) — è mostrata dal server una sola volta, non è recuperabile in
   chiaro in seguito. Se il device la perde, serve un `rotate-key` lato
   utente (§5) e riscrivere la nuova key sul device.

Errori attesi su `claim/confirm`:

| Status | Causa | Comportamento atteso del device |
|---|---|---|
| 400 | `claim_code` malformato | non ritentare, richiede intervento utente |
| 404 | `claim_code` non trovato | idem |
| 409 | `claim_code` scaduto | richiede all'utente un nuovo claim (torna a §2.1) |
| 429 | troppi tentativi | backoff, ritenta più tardi |

---

## 3. Autenticazione delle chiamate successive

Ogni chiamata del device (upload, health) porta:

```
Authorization: DeviceKey <device_api_key>
```

**Nota per hardware senza TLS affidabile** (es. ESP32 Arduino Core 3.3.7 —
vedi CLAUDE.md, TLS rotto su RSA/BIGNUM): la key viaggia su HTTP in
chiaro per questa classe di device. Non è crittograficamente forte, ma
scopa l'accesso al singolo device invece che a un intero path S3 come
nell'architettura attuale. Se il device supporta TLS in modo affidabile,
**deve** usarlo.

Risposta `401` su qualunque chiamata autenticata → la key non è più
valida (revocata, ruotata, o device con `status=revoked`). Il device deve
smettere di ritentare quella chiamata e segnalare l'errore (LED/TFT/log)
finché non riceve una nuova key via riprovisioning manuale.

---

## 4. Invio dati

### 4.1 Apertura/aggiornamento di un `session_upload`

```
POST /api/devices/me/session-uploads
Authorization: DeviceKey <device_api_key>
Content-Type: application/json

{
  "boat_id": 42,                 // opzionale per device category=boat_tracker
                                  // (default: devices.owner_boat_id); obbligatorio
                                  // per category=wearable
  "activity_id": null,           // opzionale — se assente il server ne crea/associa una
  "started_at": "2026-07-03T14:05:00Z",
  "sequence_number": 0,          // 0 = primo/unico chunk
  "is_final": true,              // true = caricamento singolo (caso standard oggi)
  "subject_type": "boat",        // "boat" | "crew_member"
  "subject_user_id": null        // valorizzato solo se subject_type=crew_member
}
```

Risposta 201:

```
{
  "session_upload_id": 987,
  "session_id": 555,
  "upload_url": "https://s3.../raw/E1/2026-07-03/E1_20260703_140500_bundle?X-Amz-...",
  "upload_url_expires_at": "2026-07-03T15:05:00Z"
}
```

Il device fa **PUT diretto** del bundle raw a `upload_url` — questa
chiamata non passa dall'API, va dritta a S3/minio (stesso schema della
sezione "Caricamento file raw e grandi" in `api-project.md`). Nessun
header `Authorization` custom su questa PUT: l'autorizzazione è nella URL
firmata stessa.

### 4.2 Caricamenti incrementali (opzionale, live tracking)

Se il device vuole inviare chunk progressivi durante la sessione invece
di un unico bundle a fine sessione:

- ogni chunk è una nuova chiamata a `POST .../session-uploads` con lo
  stesso `(session_id implicito via boat_id+timeframe)`, `sequence_number`
  incrementale, `is_final=false`
- l'ultimo chunk ha `is_final=true`
- il server consolida in `session_streams` solo dopo aver ricevuto il
  chunk con `is_final=true` per quel device in quella sessione (vedi
  `er-project.md`, nota su `session_uploads.is_final`)

Il caso "un solo caricamento a fine sessione" resta il default: basta non
implementare questa sezione e mandare sempre `sequence_number=0,
is_final=true`.

### 4.3 Chiusura/errore di un upload

```
PATCH /api/devices/me/session-uploads/{id}
Authorization: DeviceKey <device_api_key>
Content-Type: application/json

{ "is_final": true }
```

oppure, se il device rileva un fallimento locale (es. file corrotto sulla
SD prima dell'upload):

```
{ "status": "failed" }
```

### 4.4 Health snapshot

```
POST /api/devices/me/health
Authorization: DeviceKey <device_api_key>
Content-Type: application/json

{
  "battery_pct": 78,
  "battery_v": 3.91,
  "heap_free": 142300,
  "firmware_version": "2026.05.22.02",
  "uptime_s": 5423
}
```

Analogo a `_health.json` già usato dalla fleet E1 (vedi CLAUDE.md, Stage
3). Frequenza consigliata: ogni 5 minuti, o on-demand via comando
seriale/telnet (`statusup`).

---

## 5. Recovery — chiave persa o device sostituito

Il device **non** può auto-rigenerare la propria key. Serve intervento
utente dall'app:

```
POST /api/devices/{device_id}/rotate-key      (auth: owner del device)
```

Risposta: nuova `device_api_key` (una tantum, come al claim). L'utente la
riscrive sul device (config/seriale) — `external_id`, owner, nickname,
`claimed_at` restano invariati: non è un nuovo claim, solo un nuovo
segreto.

Se il device fisico viene sostituito (hardware nuovo, stesso ruolo su
barca), il flusso corretto è: `DELETE` del vecchio device (`status=
revoked`) + nuovo claim completo (§2) per il nuovo `external_id` — non un
rotate-key, perché l'`external_id` cambia.

---

## 6. Retry e backoff

- Upload fallito (PUT alla presigned URL in errore, o URL scaduta): il
  device **non deve rifare `POST .../session-uploads` con lo stesso
  `sequence_number`** se non ha ricevuto risposta 2xx dal passo
  precedente — rischia doppioni. Deve rifare la `POST` da capo per
  ottenere una nuova `upload_url` fresca, poi ritentare la PUT.
- Backoff consigliato: esponenziale, partendo da 5s, tetto a 5 minuti —
  coerente con la finestra di retry già usata per l'upload S3 diretto
  nella fleet E1 attuale.
- Le richieste di health possono fallire silenziosamente (non critiche):
  nessun retry aggressivo, si riprova al prossimo ciclo schedulato.
