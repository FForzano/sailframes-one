import type { LegalDocByLang } from "./types";

/**
 * Terms of Service — user-facing text, IT (governing) + EN.
 *
 * ⚠️ DEVELOPER NOTE (not shown to users): this is a good-faith draft grounded
 * in the applicable law (Codice Civile artt. 1341-1342, Codice del Consumo
 * D.Lgs. 206/2005, D.Lgs. 70/2003, GDPR), but it MUST be reviewed by a
 * qualified lawyer before you rely on it in production — in particular the
 * liability, unfair-terms and governing-law/forum clauses. Placeholders in
 * [square brackets] need real values (e.g. the provider's address).
 *
 * Keep TERMS_VERSION below in sync with CURRENT_TERMS_VERSION in
 * backend/legal.py — bump both whenever a change requires re-acceptance.
 */
export const TERMS_VERSION = "2026-07-22";

const PROVIDER = "Federico Forzano";
const EMAIL = "f.forzano@ieee.org";
const PEC = "f.forzano@pec.it";
const SERVICE_URL = "xgsail.com";
const GITHUB = "https://github.com/FForzano/xgsail";

export const terms: LegalDocByLang = {
  it: {
    title: "Termini e Condizioni d'uso",
    lead:
      "I presenti Termini e Condizioni d'uso (i “Termini”) disciplinano l'utilizzo del servizio XGSail nella versione ospitata (hosted) e accessibile all'indirizzo " +
      SERVICE_URL +
      " (il “Servizio”). Registrando un account o utilizzando il Servizio, l'Utente dichiara di aver letto, compreso e accettato integralmente i presenti Termini. Se non accetti i Termini, non utilizzare il Servizio.",
    sections: [
      {
        title: "1. Fornitore del Servizio e contatti",
        blocks: [
          {
            type: "p",
            text:
              "Il Servizio nella versione hosted è fornito da " +
              PROVIDER +
              ", persona fisica (il “Fornitore”).",
          },
          {
            type: "ul",
            items: [
              "Email: " + EMAIL,
              "PEC: " + PEC,
              "Indirizzo: Via Giuseppe Saragat, 1, 44122 Ferrara (FE), Italia",
            ],
          },
          {
            type: "p",
            text:
              "Le presenti informazioni sono rese anche ai sensi dell'art. 7 del D.Lgs. 70/2003 (commercio elettronico).",
          },
        ],
      },
      {
        title: "2. Oggetto e definizioni",
        blocks: [
          {
            type: "p",
            text:
              "XGSail è una piattaforma di analisi delle sessioni di vela: consente di caricare, archiviare, elaborare, rivedere e condividere dati di navigazione (tra cui tracce GPS, dati di sensori, foto e video), gestire barche, club e gruppi, e visualizzare analisi di prestazione (manovre, VMG, polari, classifiche).",
          },
          {
            type: "ul",
            items: [
              "“Utente”: la persona che registra un account o utilizza il Servizio.",
              "“Contenuti dell'Utente”: i dati, i file, le immagini e ogni altro materiale caricato o generato dall'Utente tramite il Servizio.",
              "“Versione hosted”: l'istanza del Servizio gestita dal Fornitore su " +
                SERVICE_URL +
                ", cui si applicano i presenti Termini.",
              "“Versione self-hosted”: qualsiasi installazione autonoma del software da parte di terzi (vedi punto 3): non è gestita dal Fornitore e non è soggetta ai presenti Termini.",
            ],
          },
        ],
      },
      {
        title: "3. Software open source e versioni self-hosted",
        blocks: [
          {
            type: "p",
            text:
              "Il software XGSail è open source, distribuito con licenza Apache 2.0; il codice sorgente è disponibile su " +
              GITHUB +
              ". Chiunque può installare ed eseguire una propria istanza.",
          },
          {
            type: "p",
            text:
              "I presenti Termini disciplinano esclusivamente la versione hosted gestita dal Fornitore. Per le versioni self-hosted, il soggetto che gestisce l'istanza è l'unico responsabile del servizio erogato ai propri utenti, del trattamento dei dati e della predisposizione dei propri termini e informative: il Fornitore non ha alcun controllo né responsabilità su tali istanze.",
          },
        ],
      },
      {
        title: "4. Avvertenza di sicurezza — il Servizio non è uno strumento di navigazione o di sicurezza",
        blocks: [
          {
            type: "p",
            text:
              "XGSail è uno strumento di analisi a fini sportivi, di allenamento e statistici. I dati mostrati (posizione, rotta, velocità, vento, manovre, polari e simili) sono in larga parte stimati e possono essere imprecisi, incompleti o non aggiornati in tempo reale.",
          },
          {
            type: "ul",
            items: [
              "Il Servizio NON deve essere utilizzato come strumento di navigazione, per la sicurezza in mare, per l'assistenza al processo decisionale a bordo o per finalità di soccorso.",
              "Il Servizio NON sostituisce strumenti di navigazione certificati, cartografia ufficiale, previsioni meteo-marine ufficiali né il giudizio e l'esperienza del comandante.",
              "L'Utente resta l'unico responsabile della propria sicurezza, della condotta dell'imbarcazione, del rispetto delle norme di navigazione e delle regole di regata applicabili.",
            ],
          },
        ],
      },
      {
        title: "5. Registrazione e account",
        blocks: [
          {
            type: "ul",
            items: [
              "Per accedere alle funzionalità principali è necessario registrare un account fornendo dati veritieri, esatti e aggiornati.",
              "Il Servizio è riservato agli utenti che abbiano compiuto almeno 14 anni (soglia prevista in Italia dall'art. 2-quinquies del D.Lgs. 196/2003 in attuazione dell'art. 8 GDPR). I minori di 18 anni devono utilizzare il Servizio con il coinvolgimento e il consenso di chi esercita la responsabilità genitoriale.",
              "L'Utente è responsabile della custodia delle proprie credenziali e di ogni attività svolta tramite il proprio account; deve informare tempestivamente il Fornitore in caso di uso non autorizzato.",
            ],
          },
        ],
      },
      {
        title: "6. Uso accettabile",
        blocks: [
          {
            type: "p",
            text: "L'Utente si impegna a non utilizzare il Servizio per finalità illecite o abusive. In particolare, si impegna a non:",
          },
          {
            type: "ul",
            items: [
              "caricare o diffondere contenuti illeciti, diffamatori, che violino diritti di terzi (inclusi diritti d'autore, marchi, riservatezza e dati personali altrui) o che l'Utente non ha diritto di caricare;",
              "caricare dati relativi ad altre persone (ad es. membri dell'equipaggio, altri velisti) senza averle preventivamente informate e, ove necessario, averne acquisito il consenso;",
              "compromettere la sicurezza, l'integrità o la disponibilità del Servizio (accessi non autorizzati, carichi anomali, elusione di limiti tecnici, distribuzione di malware);",
              "utilizzare il Servizio in violazione di leggi applicabili o dei diritti di terzi.",
            ],
          },
        ],
      },
      {
        title: "7. Contenuti dell'Utente",
        blocks: [
          {
            type: "p",
            text:
              "L'Utente resta titolare di ogni diritto sui propri Contenuti. Caricando Contenuti, l'Utente concede al Fornitore una licenza limitata, non esclusiva e gratuita a ospitare, archiviare, riprodurre ed elaborare tali Contenuti nella sola misura necessaria a fornire e mantenere il Servizio e a renderli disponibili secondo le impostazioni di visibilità/condivisione scelte dall'Utente (ad es. privato, club, gruppo, pubblico).",
          },
          {
            type: "p",
            text:
              "L'Utente garantisce di avere tutti i diritti necessari sui Contenuti caricati e si assume ogni responsabilità in merito. Il Fornitore non rivendica alcuna proprietà sui Contenuti dell'Utente.",
          },
        ],
      },
      {
        title: "8. Proprietà intellettuale",
        blocks: [
          {
            type: "p",
            text:
              "Il software è concesso in licenza Apache 2.0 (vedi punto 3). Restano riservati i diritti sui segni distintivi, sul nome e sui loghi “XGSail”, che non possono essere utilizzati in modo idoneo a generare confusione o a suggerire un'affiliazione non esistente, salvo quanto consentito dalla legge o da autorizzazione scritta.",
          },
        ],
      },
      {
        title: "9. Protezione dei dati personali",
        blocks: [
          {
            type: "p",
            text:
              "Il trattamento dei dati personali dell'Utente è descritto nell'Informativa Privacy, che costituisce documento separato e distinto dai presenti Termini. L'accettazione dei Termini non equivale a prestazione del consenso al trattamento dei dati: si invita a leggere l'Informativa Privacy.",
          },
        ],
      },
      {
        title: "10. Disponibilità del Servizio",
        blocks: [
          {
            type: "p",
            text:
              "Il Servizio hosted è offerto gratuitamente e “così com'è” (as is), nell'ambito di un progetto open source. Il Fornitore si adopera ragionevolmente per mantenerlo disponibile, ma non garantisce continuità, assenza di errori o conservazione illimitata dei dati, e può modificare, sospendere o cessare in tutto o in parte il Servizio, dandone, ove ragionevolmente possibile, preavviso. Si raccomanda all'Utente di conservare una copia dei dati per sé rilevanti.",
          },
        ],
      },
      {
        title: "11. Esclusione di garanzie",
        blocks: [
          {
            type: "p",
            text:
              "Nei limiti massimi consentiti dalla legge applicabile, il Servizio è fornito senza garanzie di alcun tipo, espresse o implicite, incluse garanzie di idoneità a uno scopo particolare, accuratezza dei risultati o assenza di interruzioni. Nulla nel presente punto limita i diritti inderogabili riconosciuti ai consumatori dalla legge.",
          },
        ],
      },
      {
        title: "12. Limitazione di responsabilità",
        blocks: [
          {
            type: "p",
            text:
              "Nei limiti massimi consentiti dalla legge, il Fornitore non risponde dei danni indiretti o consequenziali, della perdita di dati o di mancati risparmi derivanti dall'uso o dall'impossibilità di usare il Servizio, tenuto conto della natura gratuita dello stesso.",
          },
          {
            type: "p",
            text:
              "Resta in ogni caso ferma la responsabilità del Fornitore per dolo e colpa grave (art. 1229 c.c.), per i danni alla persona e per ogni altra ipotesi in cui la responsabilità non possa essere esclusa o limitata per legge, nonché i diritti inderogabili dei consumatori.",
          },
        ],
      },
      {
        title: "13. Manleva",
        blocks: [
          {
            type: "p",
            text:
              "L'Utente terrà indenne il Fornitore da pretese di terzi derivanti dalla violazione, da parte dell'Utente, dei presenti Termini, della legge o dei diritti di terzi, nei limiti consentiti dalla legge e salvo il caso in cui il danno sia imputabile al Fornitore.",
          },
        ],
      },
      {
        title: "14. Durata, recesso e cessazione dell'account",
        blocks: [
          {
            type: "ul",
            items: [
              "L'Utente può cessare l'uso del Servizio in qualsiasi momento e richiedere la cancellazione del proprio account.",
              "Il Fornitore può sospendere o chiudere un account in caso di violazione dei presenti Termini o della legge, o per ragioni tecniche o di sicurezza, di norma con preavviso quando ragionevolmente possibile.",
            ],
          },
        ],
      },
      {
        title: "15. Modifiche ai Termini",
        blocks: [
          {
            type: "p",
            text:
              "Il Fornitore può modificare i presenti Termini, ad esempio per adeguamenti normativi o per evoluzioni del Servizio. In caso di modifiche, l'Utente ne è informato e, per continuare a utilizzare il Servizio, gli è richiesto di accettare nuovamente la versione aggiornata: fino all'accettazione l'accesso al Servizio può essere limitato. Se l'Utente non intende accettare le modifiche, può cessare l'uso del Servizio e cancellare il proprio account.",
          },
        ],
      },
      {
        title: "16. Legge applicabile e foro competente",
        blocks: [
          {
            type: "p",
            text:
              "I presenti Termini sono regolati dalla legge italiana. Per gli Utenti che agiscono come consumatori resta ferma l'applicazione delle disposizioni inderogabili più favorevoli previste dalla legge del Paese di residenza; per le controversie è competente, in via inderogabile, il foro del luogo di residenza o domicilio del consumatore (art. 66-bis del Codice del Consumo). Per gli Utenti non consumatori, per le controversie è competente in via esclusiva il foro di Ferrara.",
          },
        ],
      },
      {
        title: "17. Clausole vessatorie",
        blocks: [
          {
            type: "p",
            text:
              "Ai sensi e per gli effetti degli artt. 1341 e 1342 c.c., l'Utente, proseguendo con l'accettazione, dichiara di approvare specificamente le clausole di cui ai punti 4 (avvertenza di sicurezza), 10 (disponibilità del Servizio), 11 (esclusione di garanzie), 12 (limitazione di responsabilità), 13 (manleva), 14 (recesso e cessazione), 15 (modifiche ai Termini) e 16 (legge applicabile e foro).",
          },
        ],
      },
      {
        title: "18. Disposizioni finali",
        blocks: [
          {
            type: "ul",
            items: [
              "L'eventuale invalidità o inefficacia di una clausola non pregiudica la validità delle restanti.",
              "I presenti Termini, unitamente all'Informativa Privacy, costituiscono l'intero accordo tra le parti in merito al Servizio.",
              "In caso di divergenza tra la versione italiana e le traduzioni, prevale la versione italiana.",
            ],
          },
        ],
      },
    ],
  },
  en: {
    title: "Terms of Service",
    lead:
      "These Terms of Service (the “Terms”) govern the use of the XGSail service in its hosted version, available at " +
      SERVICE_URL +
      " (the “Service”). By registering an account or using the Service, you confirm that you have read, understood and accepted these Terms in full. If you do not accept them, do not use the Service. This is a translation; in case of conflict the Italian version prevails.",
    sections: [
      {
        title: "1. Service provider and contacts",
        blocks: [
          {
            type: "p",
            text:
              "The hosted Service is provided by " +
              PROVIDER +
              ", a natural person (the “Provider”).",
          },
          {
            type: "ul",
            items: [
              "Email: " + EMAIL,
              "Certified email (PEC): " + PEC,
              "Address: Via Giuseppe Saragat, 1, 44122 Ferrara (FE), Italy",
            ],
          },
          {
            type: "p",
            text: "This information is also provided pursuant to art. 7 of Italian Legislative Decree 70/2003 (e-commerce).",
          },
        ],
      },
      {
        title: "2. Subject matter and definitions",
        blocks: [
          {
            type: "p",
            text:
              "XGSail is a sailing-session analytics platform: it lets you upload, store, process, review and share sailing data (including GPS tracks, sensor data, photos and videos), manage boats, clubs and groups, and view performance analysis (maneuvers, VMG, polars, leaderboards).",
          },
          {
            type: "ul",
            items: [
              "“User”: the person who registers an account or uses the Service.",
              "“User Content”: the data, files, images and any other material uploaded or generated by the User through the Service.",
              "“Hosted version”: the instance of the Service run by the Provider at " +
                SERVICE_URL +
                ", to which these Terms apply.",
              "“Self-hosted version”: any independent installation of the software by third parties (see section 3): it is not operated by the Provider and is not subject to these Terms.",
            ],
          },
        ],
      },
      {
        title: "3. Open-source software and self-hosted versions",
        blocks: [
          {
            type: "p",
            text:
              "The XGSail software is open source, licensed under Apache 2.0; the source code is available at " +
              GITHUB +
              ". Anyone may install and run their own instance.",
          },
          {
            type: "p",
            text:
              "These Terms govern only the hosted version operated by the Provider. For self-hosted versions, whoever operates the instance is solely responsible for the service provided to their users, for data processing and for putting in place their own terms and notices: the Provider has no control over and no responsibility for such instances.",
          },
        ],
      },
      {
        title: "4. Safety notice — the Service is not a navigation or safety tool",
        blocks: [
          {
            type: "p",
            text:
              "XGSail is an analytics tool for sporting, training and statistical purposes. The data shown (position, course, speed, wind, maneuvers, polars and the like) is largely estimated and may be inaccurate, incomplete or not updated in real time.",
          },
          {
            type: "ul",
            items: [
              "The Service must NOT be used as a navigation tool, for safety at sea, for on-board decision support or for rescue purposes.",
              "The Service does NOT replace certified navigation instruments, official charts, official marine weather forecasts, or the judgement and experience of the skipper.",
              "The User remains solely responsible for their own safety, for the conduct of the vessel, and for compliance with applicable navigation rules and racing rules.",
            ],
          },
        ],
      },
      {
        title: "5. Registration and account",
        blocks: [
          {
            type: "ul",
            items: [
              "Accessing the main features requires registering an account with truthful, accurate and up-to-date information.",
              "The Service is reserved for users who are at least 14 years old (the threshold set in Italy by art. 2-quinquies of Legislative Decree 196/2003 implementing art. 8 GDPR). Users under 18 must use the Service with the involvement and consent of a parent or guardian.",
              "The User is responsible for safeguarding their credentials and for all activity carried out through their account, and must promptly notify the Provider of any unauthorised use.",
            ],
          },
        ],
      },
      {
        title: "6. Acceptable use",
        blocks: [
          {
            type: "p",
            text: "The User agrees not to use the Service for unlawful or abusive purposes. In particular, the User agrees not to:",
          },
          {
            type: "ul",
            items: [
              "upload or distribute content that is unlawful, defamatory, infringes third-party rights (including copyright, trademarks, privacy and others' personal data) or that the User has no right to upload;",
              "upload data relating to other people (e.g. crew members, other sailors) without having informed them beforehand and, where necessary, obtained their consent;",
              "compromise the security, integrity or availability of the Service (unauthorised access, abnormal load, circumventing technical limits, distributing malware);",
              "use the Service in breach of applicable laws or third-party rights.",
            ],
          },
        ],
      },
      {
        title: "7. User Content",
        blocks: [
          {
            type: "p",
            text:
              "The User retains all rights in their Content. By uploading Content, the User grants the Provider a limited, non-exclusive, royalty-free licence to host, store, reproduce and process that Content only to the extent necessary to provide and maintain the Service and to make it available according to the visibility/sharing settings chosen by the User (e.g. private, club, group, public).",
          },
          {
            type: "p",
            text:
              "The User warrants that they hold all rights necessary for the Content they upload and takes full responsibility for it. The Provider claims no ownership of User Content.",
          },
        ],
      },
      {
        title: "8. Intellectual property",
        blocks: [
          {
            type: "p",
            text:
              "The software is licensed under Apache 2.0 (see section 3). Rights in the “XGSail” name, logos and distinctive signs are reserved and may not be used in a way likely to cause confusion or to suggest a non-existent affiliation, except as permitted by law or with written authorisation.",
          },
        ],
      },
      {
        title: "9. Personal data protection",
        blocks: [
          {
            type: "p",
            text:
              "The processing of the User's personal data is described in the Privacy Policy, which is a separate and distinct document from these Terms. Accepting the Terms does not amount to giving consent to data processing: please read the Privacy Policy.",
          },
        ],
      },
      {
        title: "10. Availability of the Service",
        blocks: [
          {
            type: "p",
            text:
              "The hosted Service is offered free of charge and “as is”, as part of an open-source project. The Provider makes reasonable efforts to keep it available but does not guarantee continuity, freedom from errors or unlimited data retention, and may modify, suspend or discontinue the Service in whole or in part, giving notice where reasonably possible. The User is advised to keep their own copy of data important to them.",
          },
        ],
      },
      {
        title: "11. Disclaimer of warranties",
        blocks: [
          {
            type: "p",
            text:
              "To the maximum extent permitted by applicable law, the Service is provided without warranties of any kind, express or implied, including warranties of fitness for a particular purpose, accuracy of results or uninterrupted operation. Nothing in this section limits the mandatory rights granted to consumers by law.",
          },
        ],
      },
      {
        title: "12. Limitation of liability",
        blocks: [
          {
            type: "p",
            text:
              "To the maximum extent permitted by law, the Provider shall not be liable for indirect or consequential damages, loss of data or loss of savings arising from the use of, or inability to use, the Service, taking into account its free nature.",
          },
          {
            type: "p",
            text:
              "In any event, the Provider's liability for wilful misconduct and gross negligence (art. 1229 of the Italian Civil Code), for personal injury and in any other case where liability cannot be excluded or limited by law, as well as consumers' mandatory rights, remain unaffected.",
          },
        ],
      },
      {
        title: "13. Indemnity",
        blocks: [
          {
            type: "p",
            text:
              "The User shall hold the Provider harmless from third-party claims arising from the User's breach of these Terms, of the law or of third-party rights, to the extent permitted by law and except where the damage is attributable to the Provider.",
          },
        ],
      },
      {
        title: "14. Term, withdrawal and account closure",
        blocks: [
          {
            type: "ul",
            items: [
              "The User may stop using the Service at any time and request deletion of their account.",
              "The Provider may suspend or close an account in the event of a breach of these Terms or the law, or for technical or security reasons, normally with prior notice where reasonably possible.",
            ],
          },
        ],
      },
      {
        title: "15. Changes to the Terms",
        blocks: [
          {
            type: "p",
            text:
              "The Provider may amend these Terms, for example to comply with legal changes or as the Service evolves. In case of changes, the User is informed and, to continue using the Service, is required to accept the updated version again: until acceptance, access to the Service may be restricted. If the User does not wish to accept the changes, they may stop using the Service and delete their account.",
          },
        ],
      },
      {
        title: "16. Governing law and jurisdiction",
        blocks: [
          {
            type: "p",
            text:
              "These Terms are governed by Italian law. For Users acting as consumers, the more favourable mandatory provisions of the law of their country of residence continue to apply; disputes fall within the exclusive, non-derogable jurisdiction of the courts of the consumer's place of residence or domicile (art. 66-bis of the Italian Consumer Code). For non-consumer Users, disputes fall within the exclusive jurisdiction of the courts of Ferrara, Italy.",
          },
        ],
      },
      {
        title: "17. Unfair terms",
        blocks: [
          {
            type: "p",
            text:
              "Pursuant to arts. 1341 and 1342 of the Italian Civil Code, by proceeding with acceptance the User specifically approves the clauses in sections 4 (safety notice), 10 (availability), 11 (disclaimer of warranties), 12 (limitation of liability), 13 (indemnity), 14 (withdrawal and closure), 15 (changes to the Terms) and 16 (governing law and jurisdiction).",
          },
        ],
      },
      {
        title: "18. Final provisions",
        blocks: [
          {
            type: "ul",
            items: [
              "If any clause is found invalid or ineffective, the remaining clauses remain in force.",
              "These Terms, together with the Privacy Policy, constitute the entire agreement between the parties regarding the Service.",
              "In case of discrepancy between the Italian version and any translation, the Italian version prevails.",
            ],
          },
        ],
      },
    ],
  },
};
