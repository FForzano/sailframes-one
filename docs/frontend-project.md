# Frontend project

Struttura semplificata del frontend, dopo la ristrutturazione descritta in
`er-project.md` e `api-project.md`.

## Principi

- **Login obbligatorio ovunque** — anche i contenuti "pubblici" (regate,
  club con visibilità pubblica) sono visibili solo da autenticati. Niente
  area anonima/senza account.
- Le sottosezioni elencate sotto ogni macro-pagina **non sono semplici
  tab**: sono pagine a tutti gli effetti, con URL proprio e superficie
  ampia, raggiungibili solo navigando dentro la macro-sezione — non
  compaiono come voci dirette nella action bar principale, che espone
  solo le 3 macro-sezioni.

---

## Navigazione principale (qualunque utente autenticato)

### 1. Diario

Sottopagine: **activities**, **race/regate** — "sessioni" non è più una
sottopagina di primo livello: le sessioni (una per barca) restano
un'entità di dati (`sessions`) ma in UI si vedono solo dentro il
dettaglio di un'activity, mai come lista a sé stante. Questo perché a
livello di dati un'activity raggruppa già N sessioni della stessa uscita
(vedi `er-project.md`), quindi è il livello naturale da mostrare come
elenco principale — avere due liste separate sullo stesso piano
(sessioni e activities) duplicava lo stesso concetto e confondeva
l'utente.

- **Activities** — nuova pagina di atterraggio del Diario. Elenco ad
  card/griglia (non tabella) delle proprie attività, filtrabile per
  `type` (race/training/solo) e `visibility`. Ogni card mostra
  `activities.thumbnail_image_id`: le tracce di tutte le sessioni
  dell'activity sovrapposte in colori diversi (una per barca), più
  data/tipo. Il caricamento di una nuova traccia (`sessioni/import` di
  prima) diventa un'azione dentro questa sezione, non una sottopagina di
  "sessioni".
- **Dettaglio activity** — apre da una card. Mostra i dati aggregati
  dell'activity e, sotto, un blocco per ciascuna barca partecipante
  (dati: `sessions`) — in UI etichettato **"Barche"**/**"Dettaglio
  barca"**, non "sessioni": è il nome più vicino a come l'utente pensa
  a quel blocco (chi ha navigato con quale barca in quell'uscita), pur
  restando una `session` a livello di modello. Cliccando una barca si
  apre il dettaglio sessione esistente (stats, playback, foto/video,
  crew) — stessa pagina di prima, raggiunta da un URL diverso
  (`/diario/activities/:activityId/barche/:sessionId` invece di
  `/diario/sessioni/:sessionId`).
- **Race/Regate** — pagina ampia dedicata, dashboard live/replay completa
  (mappa, leaderboard, grafici Speed/Heel/TWD, playback, laylines, wind
  rose, overlay polare, drawer dettaglio barca) — eredita le feature già
  esistenti in `web/race.html` (Tier 1-3, vedi CLAUDE.md). Nonostante sia
  "dentro" Diario, ha la superficie di una pagina a sé stante.

### 2. Gruppi

Sottopagine: **gruppi**, **clubs**

In cima alla sezione (comune a entrambe le sottopagine):
- **Notifiche/inviti pendenti** — `user_clubs`/`user_groups` con
  `status=invited`, da accettare o rifiutare.
- **Ricerca/scoperta** — club e gruppi con `visibility=public` a cui
  richiedere l'adesione.

Sottopagine:
- **Gruppi** — lista dei propri gruppi, dettaglio (membri, attività di
  gruppo). Se l'utente è `owner`/`admin` (`user_groups.role`): può creare
  attività di gruppo (`activities.type=training`, `group_id` valorizzato)
  direttamente da questa pagina — nessuna pagina di gestione separata.
- **Clubs** — lista dei propri club, dettaglio (membri, regate, barche
  stazionate). Se l'utente è `club:admin` scoped su quel club, la stessa
  pagina si apre in modalità gestione (vedi sotto) — non è una pagina
  diversa, solo azioni aggiuntive esposte in-place.

### 3. Profilo

Sottopagine: **anagrafica**, **cambio password**, **barche**, **devices**

- **Anagrafica** — dati utente (nome, email, dob, immagine profilo).
- **Cambio password**.
- **Barche** — barche possedute/gestite (`user_boats`), CRUD scoped a
  `owner`/`admin` di quella barca.
- **Devices** — device personali (`devices.owner_user_id`): avvio claim
  di un nuovo device (§ claim flow in `api-project.md`), stato/health per
  device (batteria, ultimo upload, versione firmware — da `_health.json`/
  endpoint health), rotate-key, revoca.

---

## Pagine aggiuntive per chi gestisce un club

**Nessuna pagina separata.** Aprendo la pagina di un club che si gestisce
(`club:admin` scoped a quel `club_id`), l'interfaccia espone in-place:

- Modifica anagrafica club.
- Registrazione di device ad uso dell'intero club (claim flow con
  `claim_target=owner_club_id`, non legato a una singola barca/utente) +
  vista fleet health di tutti i device del club (batteria, stato, ultimo
  upload).
- *(Work in progress, non specificato oltre)* Registrazione stazioni
  meteo (`wind_stations`) ad uso del club.
- Creazione e gestione regate: dentro lo stesso flusso, impostazione boe
  (`marks`) e inserimento risultati (`results`) — tutto resta nella
  pagina di gestione club, nessuna pagina dedicata a parte.

Chi possiede/gestisce un device (owner personale o boat:owner/admin) vede
già lo stato/health del proprio device nella sottopagina Profilo →
Devices — non serve una vista fleet dedicata per loro, quella è
specificamente per la vista aggregata a livello di club.

## Pagine aggiuntive per chi gestisce un gruppo

**Nessuna pagina separata.** Dentro la pagina del gruppo (già raggiunta
da Gruppi → gruppi), chi ha ruolo `owner`/`admin` (`user_groups.role`)
può creare attività di gruppo direttamente lì.

## Pagine aggiuntive per admin (superadmin)

- **Pagina Admin**:
  - Gestione stazioni meteo (CRUD completo `wind_stations`).
  - Gestione completa per conto di altri — accesso in scrittura a
    qualunque club/gruppo/utente/barca/device/regata, bypassando i
    controlli scoped (`club:admin`, `boat:owner`, ecc.), per supporto e
    debug.

---

## Aperto / da confermare

- Stazioni meteo di club: rimandato, "work in progress".
