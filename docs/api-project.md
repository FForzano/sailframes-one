# New API project
Questo file fornisce le direttive per le api necessarie, dopo la
ristrutturazione descritta in er-project.

Di base le api devono essere restfull e devono esistere azioni crud per tutto. I
permessi richiesti vengono descritti in seguito, in questo file.

In più, vengono descritti alcuni altri aspetti fondamentali.

## Caricamento file raw e grandi (archiviati su s3/minio)
Il caricamento e la lettura di tali files avviene tramite presigned url o
metodologie equivalenti. È dunque presente un endpoint che restituisce l'url per
la lettura/scrittura, con una scadenza e il frontend usa tale url per le
operazioni.
Il processing dei dati grezzi viene gestito tramite microservizi (lambda o
equivalente), a seguito di un evento del sistema di archiviazione (s3/minio).
Tale microservizio si occupa anche di gestire lo stato di elaborazione nel db.

## Fetching api meteo/vento
Il fetching delle api scelte avviene periodicamente, con cadenza parametrizzata
e scelta (scritto nel servizio, per provider)

## Ruoli e permessi per classe di API

Due livelli di autorizzazione, non uno solo:

1. **RBAC scoped** (`roles`/`permissions`/`role_permissions`/`user_roles`,
   quest'ultima con `scope_club_id` opzionale) — per ruoli istituzionali:
   `superadmin` (globale, bypassa tutto), `club_admin` (scoped a un club),
   `race_officer` (scoped a un club, gestisce regate/risultati/marks per
   conto del club). Si applica alle risorse "di club": clubs, regattas,
   race_days, races, results, marks.
2. **Ownership per-risorsa** (`user_boats.role`, `user_groups.role`) — per
   risorse personali/di barca: niente permission-check centralizzato, la
   relazione stessa dice chi può fare cosa (owner = CRUD pieno, admin =
   write senza delete, visitor/member = sola lettura).

Notazione usata sotto: `pub` = chiunque anche non autenticato · `auth` =
utente autenticato qualsiasi · `self` = proprietario del record personale ·
`boat:owner`/`boat:admin` = `user_boats.role` · `group:owner`/`group:admin`
= `user_groups.role` · `club:admin`/`race_officer` = ruolo scoped via
`user_roles` · `superadmin` = `users.is_superadmin` · `system` = solo
processo/microservizio interno, nessun endpoint utente.

### Account & auth

| Risorsa | Create | Read | Update | Delete |
|---|---|---|---|---|
| `users` | pub (registrazione) | self, superadmin | self, superadmin | self (soft, `status=deleted`), superadmin |
| `auth_refresh_tokens` | system (flow di login/refresh) | — (mai esposto via API diretta) | — | system (revoca) |

### RBAC admin

| Risorsa | Create | Read | Update | Delete |
|---|---|---|---|---|
| `roles`, `permissions`, `role_permissions` | superadmin | superadmin | superadmin | superadmin |
| `user_roles` | superadmin (ruoli globali) · club:admin (solo ruoli scoped al proprio `scope_club_id`, mai `superadmin`) | self, club:admin scoped, superadmin | come create | come create |

### Club & membership

| Risorsa | Create | Read | Update | Delete |
|---|---|---|---|---|
| `clubs` | auth (diventa club:admin del nuovo club) | pub | club:admin scoped, superadmin | club:admin scoped (`is_active=false`, mai hard delete), superadmin |
| `user_clubs` | auth (richiesta di adesione, `status=invited`) | self, club:admin scoped | club:admin scoped (approva/rimuove) | self (esce), club:admin scoped |

### Regate

| Risorsa | Create | Read | Update | Delete |
|---|---|---|---|---|
| `regattas`, `race_days`, `races` | club:admin/race_officer scoped al `club_id`, superadmin | pub | club:admin/race_officer scoped, superadmin | club:admin/race_officer scoped, superadmin |
| `results` | club:admin/race_officer scoped, superadmin | pub | club:admin/race_officer scoped, superadmin | club:admin/race_officer scoped, superadmin |
| `marks` | creatore dell'`activity` collegata, o club:admin/race_officer se `activity.type=race` | segue `visibility` dell'activity | come create | come create |

### Barche & dispositivi

| Risorsa | Create | Read | Update | Delete |
|---|---|---|---|---|
| `boat_classes` | superadmin | pub | superadmin | superadmin |
| `boats` | auth (diventa `boat:owner`) | pub (dati base); dettagli sensibili (`cert_id`/`mbsa_id`) solo boat:owner/admin/crew | boat:owner/admin | boat:owner |
| `user_boats` | boat:owner/admin (aggiunge un membro) | membri della barca | boat:owner (cambia ruolo) | boat:owner/admin, o self (esce) |
| `device_types` | superadmin | pub | superadmin | superadmin |
| `devices` | auth via claim flow (`claim_code`) — vedi sezione "Registrazione device e ingestion dati" | owner (`owner_user_id`) o boat:owner/admin (`owner_boat_id`) | owner/boat:owner/admin (nickname, ecc.) | owner/boat:owner (revoca) |
| `imports` | auth | `uploaded_by` | `uploaded_by` | `uploaded_by` |

### Gruppi

| Risorsa | Create | Read | Update | Delete |
|---|---|---|---|---|
| `groups` | auth (diventa `group:owner`) | pub se `visibility=public`, altrimenti solo membri | group:owner/admin | group:owner |
| `user_groups` | group:owner/admin (invita), o self se il gruppo è pubblico | membri | group:owner (cambia ruolo) | group:owner/admin, o self (esce) |

### Attività & sessioni

| Risorsa | Create | Read | Update | Delete |
|---|---|---|---|---|
| `activities` | auth (`created_by`) | segue `visibility` (public/club/group/private) incrociata con club:admin/membro gruppo/creatore | `created_by`, club:admin scoped se `club_id` valorizzato, superadmin | come update |
| `sessions` | system (alla ricezione del primo `session_upload`), o creatore activity | segue visibility dell'activity padre | boat:owner/admin, creatore activity | boat:owner, creatore activity |
| `session_crew` | boat:owner/admin, o self se invitato | segue visibility della sessione | — | boat:owner/admin, o self (si rimuove) |
| `session_photos`, `session_videos` | chi è in `session_crew` per quella sessione, o boat:owner/admin | segue visibility | — | `created_by`, o boat:owner/admin |
| `session_uploads` | il device stesso (token/API key del device) o utente per import manuale | boat:owner/admin/crew | — (log di processing) | — |
| `session_streams`, `session_stats` | system (microservizio di processing) | boat:owner/admin/crew, secondo visibility | — | — |

### Meteo/vento

| Risorsa | Create | Read | Update | Delete |
|---|---|---|---|---|
| `wind_stations`, `wind_observations` | system (job di fetching periodico) | pub | system | system |

### Media (images/files)

Nessun endpoint CRUD diretto: l'accesso (presigned URL) è mediato dalla
risorsa padre — per caricare una `boat_photos` serve il permesso di update
su quella `boats`, per una `session_photos`/`session_videos` serve essere
in `session_crew` o boat:owner/admin di quella sessione. `images`/`files`
non hanno un proprio livello di permesso indipendente.

## Registrazione device e ingestion dati

Tre flussi distinti, con modalità di autenticazione diverse perché gli
attori sono diversi: un utente loggato dall'app, un device hardware con
vincoli di connettività (vedi CLAUDE.md — TLS non affidabile su ESP32,
upload spesso su reti note del circolo), o un utente che carica un file
già pronto (GPX/FIT) da un altro sistema.

### 1. Registrazione di un device (claim flow)

1. `POST /api/devices/claims` (auth: utente) — body `{device_type_id,
   nickname?, claim_target: {owner_user_id | owner_boat_id}}`. Crea (o
   riusa se già `unclaimed`) una riga `devices` con `claim_code` random
   e `claim_code_expires_at` (~15 min). Risposta: `{claim_code,
   expires_at}` — il codice va comunicato al device fuori banda (es.
   scritto in `config.txt` via SD, o inserito da un'interfaccia seriale/
   web del device, a seconda del `device_type`).
2. `POST /api/devices/claim/confirm` — **nessuna auth utente**, il
   possesso del `claim_code` valido è la credenziale. Body:
   `{external_id, claim_code}`. Il server valida scadenza, imposta
   `devices.external_id`, `status=claimed`, `claimed_at`, `claimed_by`
   (l'utente che ha generato il codice al passo 1), applica
   `owner_user_id`/`owner_boat_id` da `claim_target`. Genera **una
   tantum** un `device_api_key` (mostrato solo in questa risposta,
   salvato lato server solo come hash) — è la credenziale che il device
   userà per tutte le chiamate successive.
3. `POST /api/devices/{id}/rotate-key` (auth: owner) — invalida la key
   corrente e ne emette una nuova (sostituzione hardware, sospetto di
   compromissione).
4. `DELETE /api/devices/{id}` (auth: owner) — `status=revoked`, la key
   esistente smette di essere accettata.

**Decisione che risolve un punto aperto precedente:** un device deve
completare il claim (ed ottenere la sua `device_api_key`) **prima** di
poter chiamare le API di upload — niente più auto-creazione `unclaimed`
al primo upload "orfano". Semplifica il modello (non serve più gestire
riconciliazione a posteriori) al costo di richiedere il claim come primo
step obbligato all'atto pratico (setup iniziale del device, una tantum).

**Nota sicurezza/trasporto:** per hardware come l'E1, dove TLS su ESP32
Arduino Core non è affidabile (vedi CLAUDE.md, gotcha TLS), la
`device_api_key` viaggerebbe comunque su HTTP in chiaro per quella
classe di device — non è una protezione crittografica forte, ma è
comunque un miglioramento rispetto alla policy S3 attuale (PUT
anonimo su tutto `raw/E1/*`): la key scopa l'accesso al singolo device
invece che all'intero path del prodotto.

### 2. API usate dal device per caricare i dati

Auth: header `Authorization: DeviceKey <device_api_key>` (anche su
HTTP semplice, vedi nota sopra).

- `POST /api/devices/me/session-uploads` — body:
  `{boat_id, activity_id?, started_at, sequence_number, is_final,
  subject_type, subject_user_id?}`. Per device `category=boat_tracker`
  (es. E1) `boat_id` è di default `devices.owner_boat_id`; per
  `wearable` va dichiarato esplicitamente (un orologio può passare da
  una barca all'altra). Crea/aggiorna la riga `session_uploads`
  (creando `sessions`/`activities` se non esistono ancora per quella
  combinazione boat+timeframe) e risponde con una presigned URL per il
  PUT del bundle raw (stesso meccanismo della sezione "Caricamento file
  raw e grandi").
- Il device fa il PUT diretto alla presigned URL (fuori dall'API).
- `PATCH /api/devices/me/session-uploads/{id}` — per marcare
  `is_final=true` sul chunk conclusivo (chiude la sessione lato device,
  vedi `sequence_number`/`is_final` in `session_uploads`) o segnalare
  `status=failed` in caso di errore.
- `POST /api/devices/me/health` — snapshot stato device (batteria,
  heap, versione firmware...), analogo a `_health.json` già usato dalla
  fleet E1 oggi.

### 3. API per caricare dati manualmente (import)

Auth: utente loggato.

1. `POST /api/imports` — body `{original_filename}`. Crea `imports`
   (`status=pending`, `uploaded_by`=utente corrente), risponde con
   presigned URL di upload.
2. L'utente fa PUT diretto alla presigned URL.
3. `POST /api/imports/{id}/complete` (auth: `uploaded_by`) — segnala
   fine upload e i metadati di destinazione: a quale `boat_id` e
   `activity_id`/sessione va associato il file (nuova sessione o
   esistente), più `subject_type`/`subject_user_id` se rappresenta un
   membro dell'equipaggio. Il microservizio di processing crea il
   `session_uploads` (`source_type=manual_import`, `import_id`) e
   procede come per un upload da device.
4. `GET /api/imports/{id}` (auth: `uploaded_by`) — stato di processing
   (`pending|processed|failed`).

