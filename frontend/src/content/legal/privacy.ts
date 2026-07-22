import type { LegalDocByLang } from "./types";

/**
 * Privacy Policy (informativa ex artt. 13-14 GDPR) — IT (governing) + EN.
 *
 * ⚠️ DEVELOPER NOTE (not shown to users): good-faith draft grounded in the
 * GDPR (Reg. UE 2016/679) and D.Lgs. 196/2003 as amended by D.Lgs. 101/2018.
 * It MUST be reviewed by a qualified professional and reconciled with the
 * ACTUAL processing you carry out in production (hosting/storage providers,
 * any non-EU transfers, retention periods, analytics/cookies). Placeholders in
 * [square brackets] need real values.
 *
 * Keep PRIVACY_VERSION in sync with CURRENT_PRIVACY_VERSION in backend/legal.py.
 */
export const PRIVACY_VERSION = "2026-07-22";

const CONTROLLER = "Federico Forzano";
const EMAIL = "f.forzano@ieee.org";
const PEC = "f.forzano@pec.it";
const SERVICE_URL = "xgsail.com";

export const privacy: LegalDocByLang = {
  it: {
    title: "Informativa sulla Privacy",
    lead:
      "La presente Informativa descrive il trattamento dei dati personali degli utenti del servizio XGSail nella versione ospitata (hosted) accessibile all'indirizzo " +
      SERVICE_URL +
      ", ai sensi degli artt. 13 e 14 del Regolamento (UE) 2016/679 (“GDPR”). L'Informativa è documento distinto dai Termini e Condizioni d'uso.",
    sections: [
      {
        title: "1. Titolare del trattamento",
        blocks: [
          {
            type: "p",
            text:
              "Titolare del trattamento per la versione hosted è " +
              CONTROLLER +
              " (email: " +
              EMAIL +
              "; PEC: " +
              PEC +
              "; indirizzo: Via Giuseppe Saragat, 1, 44122 Ferrara (FE), Italia).",
          },
          {
            type: "p",
            text:
              "Per le istanze self-hosted gestite da terzi, titolare del trattamento è il soggetto che gestisce l'istanza: la presente Informativa non si applica a tali installazioni.",
          },
        ],
      },
      {
        title: "2. Categorie di dati trattati",
        blocks: [
          {
            type: "ul",
            items: [
              "Dati dell'account: indirizzo email, password (conservata solo in forma di hash), nome e cognome (se forniti), data di nascita (facoltativa), immagine del profilo (facoltativa), preferenze (es. unità di misura, lingua).",
              "Dati di attività e sessione: tracce GPS (dati di geolocalizzazione), dati di sensori, orari, parametri di navigazione e prestazione, foto e video caricati.",
              "Dati relativi a barche, club, gruppi ed equipaggi gestiti dall'Utente.",
              "Dati tecnici e di utilizzo: indirizzo IP, log di sistema, informazioni sul dispositivo/browser, cookie e identificatori tecnici necessari al funzionamento.",
              "Dati di terzi caricati dall'Utente: se l'Utente inserisce dati riferibili ad altre persone (ad es. membri dell'equipaggio), è responsabile di averle informate e, ove necessario, di averne acquisito il consenso.",
            ],
          },
        ],
      },
      {
        title: "3. Finalità e basi giuridiche",
        blocks: [
          {
            type: "ul",
            items: [
              "Fornire il Servizio e gestire l'account, incluse archiviazione ed elaborazione dei contenuti caricati e le funzioni di condivisione — base giuridica: esecuzione del contratto (art. 6.1.b GDPR).",
              "Garantire la sicurezza, prevenire abusi e usi impropri, e assicurare il corretto funzionamento tecnico — base giuridica: legittimo interesse del Titolare (art. 6.1.f GDPR).",
              "Adempiere a obblighi di legge e gestire eventuali contestazioni — base giuridica: obbligo legale (art. 6.1.c) e legittimo interesse (art. 6.1.f).",
              "Riscontrare le richieste di esercizio dei diritti dell'interessato — base giuridica: obbligo legale (art. 6.1.c).",
            ],
          },
          {
            type: "p",
            text:
              "Il Titolare non effettua profilazione né attività di marketing tramite il Servizio e non vende i dati personali a terzi.",
          },
        ],
      },
      {
        title: "4. Dati di geolocalizzazione",
        blocks: [
          {
            type: "p",
            text:
              "Le tracce GPS caricate o registrate dall'Utente costituiscono dati personali di geolocalizzazione. Sono trattate esclusivamente per fornire le funzioni di analisi, replay e condivisione della sessione, secondo le impostazioni di visibilità scelte dall'Utente. Il caricamento di tali dati è volontario e sotto il controllo dell'Utente.",
          },
        ],
      },
      {
        title: "5. Natura del conferimento",
        blocks: [
          {
            type: "p",
            text:
              "Il conferimento dei dati dell'account (in particolare l'email) è necessario per registrarsi e utilizzare il Servizio; il mancato conferimento impedisce la creazione dell'account. Il conferimento degli altri dati (es. tracce, foto, dati anagrafici facoltativi) è libero e legato alle funzioni che l'Utente sceglie di utilizzare.",
          },
        ],
      },
      {
        title: "6. Destinatari e responsabili del trattamento",
        blocks: [
          {
            type: "p",
            text:
              "Allo stato, l'applicazione e i dati sono ospitati su un server gestito direttamente dal Titolare: non sono coinvolti fornitori di hosting o di archiviazione terzi in qualità di responsabili del trattamento. I dati possono essere comunicati esclusivamente:",
          },
          {
            type: "ul",
            items: [
              "a eventuali fornitori tecnici che dovessero rendersi in futuro strettamente necessari all'erogazione del Servizio, previa loro nomina a responsabili del trattamento ai sensi dell'art. 28 GDPR (in tal caso la presente Informativa sarà aggiornata);",
              "ad autorità pubbliche, ove richiesto dalla legge.",
            ],
          },
          {
            type: "p",
            text: "I dati non sono diffusi né ceduti a terzi per finalità commerciali.",
          },
        ],
      },
      {
        title: "7. Trasferimenti extra-UE",
        blocks: [
          {
            type: "p",
            text:
              "I dati sono trattati e conservati su un server situato nell'Unione Europea (Italia): allo stato non è previsto alcun trasferimento verso Paesi terzi (extra SEE). Qualora, in futuro, il trattamento comportasse un trasferimento extra-SEE, esso avverrà solo in presenza di adeguate garanzie ai sensi degli artt. 44 e ss. GDPR (ad es. decisione di adeguatezza o Clausole Contrattuali Standard) e la presente Informativa sarà aggiornata.",
          },
        ],
      },
      {
        title: "8. Periodo di conservazione",
        blocks: [
          {
            type: "p",
            text:
              "I dati dell'account e i contenuti sono conservati per il tempo in cui l'account resta attivo. In caso di cancellazione dell'account, i dati sono cancellati o resi anonimi entro tempi tecnici ragionevoli, salvo l'obbligo o il diritto di conservarli per il tempo necessario ad adempiere obblighi di legge o a far valere/difendere un diritto. I log tecnici sono conservati per un periodo limitato per finalità di sicurezza.",
          },
        ],
      },
      {
        title: "9. Diritti dell'interessato",
        blocks: [
          {
            type: "p",
            text: "L'Utente può in ogni momento esercitare i diritti previsti dagli artt. 15-22 GDPR:",
          },
          {
            type: "ul",
            items: [
              "accesso ai propri dati e loro rettifica;",
              "cancellazione (“diritto all'oblio”) e limitazione del trattamento;",
              "opposizione al trattamento fondato sul legittimo interesse;",
              "portabilità dei dati;",
              "revoca del consenso, ove il trattamento sia basato sul consenso, senza pregiudizio per la liceità del trattamento precedente.",
            ],
          },
          {
            type: "p",
            text: "Le richieste possono essere inviate ai contatti del Titolare indicati al punto 1.",
          },
        ],
      },
      {
        title: "10. Reclamo all'autorità di controllo",
        blocks: [
          {
            type: "p",
            text:
              "L'interessato ha diritto di proporre reclamo all'autorità di controllo competente. In Italia è il Garante per la protezione dei dati personali (www.garanteprivacy.it). Gli utenti residenti in altri Stati membri dell'UE possono rivolgersi all'autorità di controllo del proprio Paese.",
          },
        ],
      },
      {
        title: "11. Minori",
        blocks: [
          {
            type: "p",
            text:
              "Il Servizio non è destinato ai minori di 14 anni. Se un genitore o tutore ritiene che un minore abbia fornito dati senza adeguato consenso, può contattare il Titolare per la cancellazione.",
          },
        ],
      },
      {
        title: "12. Cookie e tecnologie simili",
        blocks: [
          // DEVELOPER NOTE (not shown to users): se in futuro verranno
          // introdotti cookie non tecnici/di analisi o di terze parti,
          // aggiornare questa sezione e predisporre un meccanismo di consenso
          // (cookie banner) conforme al provvedimento del Garante.
          {
            type: "p",
            text:
              "Il Servizio utilizza cookie e archiviazione locale strettamente necessari al funzionamento (ad es. per l'autenticazione e la sicurezza), che non richiedono consenso.",
          },
        ],
      },
      {
        title: "13. Modifiche all'Informativa",
        blocks: [
          {
            type: "p",
            text:
              "La presente Informativa può essere aggiornata nel tempo. In caso di modifiche rilevanti, l'Utente ne è informato e gli può essere richiesto di prenderne nuovamente visione al successivo accesso. La data di efficacia e la versione sono indicate in cima al documento.",
          },
        ],
      },
    ],
  },
  en: {
    title: "Privacy Policy",
    lead:
      "This Privacy Policy describes how personal data of users of the XGSail service, in its hosted version available at " +
      SERVICE_URL +
      ", is processed, pursuant to arts. 13 and 14 of Regulation (EU) 2016/679 (“GDPR”). This Policy is a separate document from the Terms of Service. This is a translation; in case of conflict the Italian version prevails.",
    sections: [
      {
        title: "1. Data controller",
        blocks: [
          {
            type: "p",
            text:
              "The data controller for the hosted version is " +
              CONTROLLER +
              " (email: " +
              EMAIL +
              "; certified email/PEC: " +
              PEC +
              "; address: Via Giuseppe Saragat, 1, 44122 Ferrara (FE), Italy).",
          },
          {
            type: "p",
            text:
              "For self-hosted instances operated by third parties, the data controller is whoever operates the instance: this Policy does not apply to such installations.",
          },
        ],
      },
      {
        title: "2. Categories of data processed",
        blocks: [
          {
            type: "ul",
            items: [
              "Account data: email address, password (stored only as a hash), first and last name (if provided), date of birth (optional), profile picture (optional), preferences (e.g. units, language).",
              "Activity and session data: GPS tracks (geolocation data), sensor data, timestamps, navigation and performance parameters, uploaded photos and videos.",
              "Data about boats, clubs, groups and crews managed by the User.",
              "Technical and usage data: IP address, system logs, device/browser information, cookies and technical identifiers necessary for operation.",
              "Third-party data uploaded by the User: if the User enters data relating to other people (e.g. crew members), the User is responsible for having informed them and, where necessary, obtained their consent.",
            ],
          },
        ],
      },
      {
        title: "3. Purposes and legal bases",
        blocks: [
          {
            type: "ul",
            items: [
              "Providing the Service and managing the account, including storing and processing uploaded content and sharing features — legal basis: performance of a contract (art. 6.1.b GDPR).",
              "Ensuring security, preventing abuse and misuse, and ensuring correct technical operation — legal basis: the controller's legitimate interest (art. 6.1.f GDPR).",
              "Complying with legal obligations and handling any disputes — legal basis: legal obligation (art. 6.1.c) and legitimate interest (art. 6.1.f).",
              "Responding to requests to exercise data-subject rights — legal basis: legal obligation (art. 6.1.c).",
            ],
          },
          {
            type: "p",
            text: "The controller does not carry out profiling or marketing through the Service and does not sell personal data to third parties.",
          },
        ],
      },
      {
        title: "4. Geolocation data",
        blocks: [
          {
            type: "p",
            text:
              "GPS tracks uploaded or recorded by the User are geolocation personal data. They are processed solely to provide session analysis, replay and sharing features, according to the visibility settings chosen by the User. Uploading such data is voluntary and under the User's control.",
          },
        ],
      },
      {
        title: "5. Nature of the provision of data",
        blocks: [
          {
            type: "p",
            text:
              "Providing account data (in particular the email address) is necessary to register and use the Service; failure to provide it prevents account creation. Providing other data (e.g. tracks, photos, optional profile details) is optional and tied to the features the User chooses to use.",
          },
        ],
      },
      {
        title: "6. Recipients and processors",
        blocks: [
          {
            type: "p",
            text:
              "At present, the application and the data are hosted on a server operated directly by the controller: no third-party hosting or storage providers are involved as data processors. Data may be disclosed only:",
          },
          {
            type: "ul",
            items: [
              "to any technical providers that may in future become strictly necessary to deliver the Service, once appointed as data processors under art. 28 GDPR (in which case this Policy will be updated);",
              "to public authorities, where required by law.",
            ],
          },
          {
            type: "p",
            text: "Data is not disseminated or transferred to third parties for commercial purposes.",
          },
        ],
      },
      {
        title: "7. Transfers outside the EU",
        blocks: [
          {
            type: "p",
            text:
              "Data is processed and stored on a server located in the European Union (Italy): at present no transfer to third countries (outside the EEA) takes place. Should processing in future involve a transfer outside the EEA, it will only occur under appropriate safeguards pursuant to arts. 44 et seq. GDPR (e.g. an adequacy decision or Standard Contractual Clauses), and this Policy will be updated.",
          },
        ],
      },
      {
        title: "8. Retention period",
        blocks: [
          {
            type: "p",
            text:
              "Account data and content are retained for as long as the account remains active. If the account is deleted, data is deleted or anonymised within a reasonable technical timeframe, save for any obligation or right to retain it as necessary to comply with legal obligations or to establish/defend a legal claim. Technical logs are kept for a limited period for security purposes.",
          },
        ],
      },
      {
        title: "9. Data-subject rights",
        blocks: [
          {
            type: "p",
            text: "The User may at any time exercise the rights under arts. 15-22 GDPR:",
          },
          {
            type: "ul",
            items: [
              "access to and rectification of their data;",
              "erasure (“right to be forgotten”) and restriction of processing;",
              "objection to processing based on legitimate interest;",
              "data portability;",
              "withdrawal of consent, where processing is based on consent, without affecting the lawfulness of prior processing.",
            ],
          },
          {
            type: "p",
            text: "Requests can be sent to the controller's contacts indicated in section 1.",
          },
        ],
      },
      {
        title: "10. Complaint to a supervisory authority",
        blocks: [
          {
            type: "p",
            text:
              "The data subject has the right to lodge a complaint with the competent supervisory authority. In Italy this is the Garante per la protezione dei dati personali (www.garanteprivacy.it). Users resident in other EU Member States may contact the supervisory authority of their own country.",
          },
        ],
      },
      {
        title: "11. Minors",
        blocks: [
          {
            type: "p",
            text:
              "The Service is not intended for children under 14. If a parent or guardian believes that a minor has provided data without adequate consent, they may contact the controller for deletion.",
          },
        ],
      },
      {
        title: "12. Cookies and similar technologies",
        blocks: [
          // DEVELOPER NOTE (not shown to users): if non-technical/analytics or
          // third-party cookies are introduced in future, update this section
          // and put in place a consent mechanism (cookie banner) compliant with
          // the Italian DPA (Garante) guidance.
          {
            type: "p",
            text:
              "The Service uses cookies and local storage that are strictly necessary for operation (e.g. for authentication and security), which do not require consent.",
          },
        ],
      },
      {
        title: "13. Changes to this Policy",
        blocks: [
          {
            type: "p",
            text:
              "This Policy may be updated over time. In case of significant changes, the User is informed and may be asked to review it again on their next visit. The effective date and version are shown at the top of the document.",
          },
        ],
      },
    ],
  },
};
