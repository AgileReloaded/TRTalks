# TRTalks

Applicazione locale che raccoglie più skill di conversazione. La prima è
**TRStory**, dedicata alle case histories e ai resoconti per TechReloaded.
Funziona nell’app Codex, senza
plugin ChatGPT. Progetto distinto da TRInterview/TRConversations.

Versione infrastruttura: **0.3.0a1**. Pacchetto e strumenti implementati e provati
localmente. Installazione da Internet, riconoscimento nella tua app, intervista
vocale e consegna email remota restano da collaudare. Nessuna email è stata
inviata durante lo sviluppo. Vedere [struttura e verifiche](docs/SKILL-DI-CONVERSAZIONE.md).

## Installazione per i colleghi

La distribuzione usa release HTTPS e checksum SHA-256, seguendo il meccanismo
letto in Websmith. Servono macOS/Linux, Python 3.9+ e curl. Nessun pacchetto pip,
Node.js o Git è richiesto a chi installa. Codex va installato e autenticato a parte.

La release comprende `setup.sh`, `trtalks.zip`, `SHA256SUMS`, `release.json` e
una pagina di istruzioni `index.html`. Il repository remoto scelto è
`AgileReloaded/TRTalks`; la release installabile non è ancora pubblicata e verificata.
La [pagina di installazione](docs/installazione.html) viene completata dal builder
con l’URL effettivo, senza dover farlo digitare ai colleghi.

Dopo la pubblicazione, il comando sarà quello generato sulla pagina:

```bash
curl --proto '=https' --proto-redir '=https' -fsSL 'URL_RELEASE/setup.sh' | bash
```

`URL_RELEASE` è un segnaposto, non un URL attivo. La copia di setup contenuta
nella release ha già la base download configurata. Il setup sorgente può essere
usato impostando `TRTALKS_RELEASE_URL`.

L’installer crea `~/TRTalks`, il runtime in `.trtalks/app/runtime/` e tutte le
skill dichiarate nel catalogo in `.agents/skills/ID/`. TRStory si trova in
`~/TRTalks/.agents/skills/trstory`. Le altre skill del computer restano invariate.
Non modifica il profilo della shell o la configurazione globale di Codex.
Aprire `~/TRTalks` come progetto nell’app e scrivere:

> Usa $trstory per raccogliere un caso TechReloaded.

Il comando `~/TRTalks/trtalks skills` elenca le conversazioni disponibili.
Ogni skill definisce domande, regole e formato; TRTalks fornisce gli strumenti
comuni. Se la richiesta è generica e ci sono più skill, l’assistente chiede quale
usare. Le istruzioni di progetto vengono create solo se `AGENTS.md` non esiste.

Si può scegliere la cartella con `TRTALKS_HOME`. La prima installazione non
sovrascrive una skill esistente e lascia l’invio disabilitato.

## Aggiornamento e disinstallazione

```bash
~/TRTalks/trtalks --version
~/TRTalks/trtalks update --dry-run
~/TRTalks/trtalks update
~/TRTalks/trtalks uninstall
```

`update` scarica dalla sorgente memorizzata in prima installazione, verifica
checksum e manifest, prova l’avvio della nuova versione e aggiorna runtime e skill dichiarate.
Se un passaggio fallisce, ripristina il gruppo precedente.
Non effettua downgrade. Conserva configurazione, eventuali credenziali locali,
bozze, stato delle consegne e `*.local.md`. Se un file gestito è stato modificato
o compare un file estraneo si ferma, senza sovrascriverlo. Le personalizzazioni
editoriali vanno in `*.local.md` o `.trtalks/overrides/ID/`.

Una copia precedente viene conservata in `.trtalks/backups/`. Un errore durante
la sostituzione ripristina il programma precedente. `--dry-run` scarica e controlla
senza scrivere nell’installazione. Le operazioni di manutenzione sono serializzate.

`uninstall` sposta runtime e skill gestite nei backup e rimuove il launcher non
personalizzato. Conserva cartella di lavoro, impostazioni e consegne e non tocca
altre skill. Reinstallare dopo una disinstallazione conserva la configurazione.

Il checksum controlla la corrispondenza con la release scaricata; non è una
firma indipendente del distributore.

## Consegna alla redazione

Il backend esistente è `https://techreloaded.it/shared/php/trdocument-mcp.php`.
Lo script gli invia una POST JSON-RPC: non richiede di configurare MCP in Codex
e non richiede modifiche al PHP. Autenticazione assente nel sorgente verificato;
nessuna credenziale è inclusa nel pacchetto.

Per configurare il nome e controllare il backend senza email:

```bash
~/TRTalks/trtalks configure --name 'Nome Cognome'
~/TRTalks/trtalks status
~/TRTalks/trtalks probe
```

`status` chiama solo `connection-status`. `probe` usa esclusivamente il PHP di
prova, che non salva e non invia email. L’attivazione dell’invio è una scelta
esplicita di configurazione: `trtalks configure --enable-send`. Non spedisce da sé.
L’agente può configurare l’invio nell’ambito di una richiesta già autorizzata,
senza chiedere una seconda autorizzazione alla stessa consegna.

L’assistente mostra il file completo, lo rende disponibile e raccoglie l’unica
autorizzazione alla consegna di quella versione a `info@techreloaded.it`, inclusi
gli eventuali dettagli riservati alla redazione. Poi esegue direttamente:

```text
trtalks dry-run /percorso/intervista-nome.md
trtalks send /percorso/intervista-nome.md --approved-sha256 HASH --authorization 'Riferimento all’autorizzazione ricevuta'
```

Questi sono comandi dell’agente: l’intervistato non deve eseguire l’invio.
`dry-run` non usa la rete. L’hash identifica i byte autorizzati; il testo
dell’autorizzazione registra la decisione conversazionale, non è un token server.

Prima della rete lo script salva payload esatto, endpoint, ID e autorizzazione
in `.trtalks/deliveries`. Conserva i byte originali UTF-8, anche le terminazioni
di riga. Rifiuta un documento modificato rispetto all’hash autorizzato.
Il lock locale impedisce consegne contemporanee.

Un documento già accettato restituisce la ricevuta salvata senza reinviarlo.
Dopo timeout o interruzione non crea un nuovo ID. `trtalks retry REQUEST_ID`
riutilizza il payload congelato, senza leggere eventuali modifiche successive
alla bozza e senza richiedere la stessa approvazione. Nessun retry automatico
in ciclo. I conflitti o gli stati server che richiedono revisione bloccano
ulteriori tentativi; anche i tentativi più vecchi di 150 giorni vengono fermati.

`backend_accepted:true` significa accettazione per la consegna, non email
arrivata. Negli esiti incerti vale `null`; `email_delivery` resta `unconfirmed`.
HTTP 200 da solo non basta: vengono controllati anche JSON-RPC, `isError`,
`http_status`, `submission` e ID. Bozza, payload e ricevute rimangono disponibili
se il tentativo fallisce.

## Struttura

| Percorso | Responsabilità |
| --- | --- |
| `conversations.json` | Catalogo delle conversazioni e file da distribuire per ciascuna |
| `skills/trstory/SKILL.md` | TRStory: raccolta di case histories |
| `skills/trstory/references/` | Domande e regole del resoconto |
| `skills/trstory/assets/resoconto.md` | Modello Markdown |
| `runtime/trtalks.py` | CLI, elenco skill, percorsi e configurazione |
| `runtime/send_document.py` | Consegna autorizzata e ritentativi condivisi |
| `runtime/delivery.py` | Prova HTTP fittizia senza email |
| `runtime/manage.py` | Installazione, update, migrazione e uninstall |
| `runtime/references/` | Contratto backend e procedura di consegna condivisi |
| `setup.sh` | Bootstrap HTTPS |
| `scripts/build_release.py` | Pacchetto deterministico con lista esplicita dei file |
| `scripts/publish.py` | Pubblicazione da Terminale su GitHub, con test e verifica asset |
| `scripts/draft_release.py` | Preparazione di una release GitHub in bozza |
| `docs/installazione.html` | Pagina per i colleghi |
| `tests/` | Test su filesystem, client e contratto PHP |

Nel progetto installato `.trtalks/config.local.json`, `.trtalks/deliveries/`,
`.trtalks/overrides/`, `drafts/` e `artifacts/` restano fuori dai file distribuiti.
Payload e stato sono file privati, con permessi 600 nelle directory create a 700.

## Sviluppo e pubblicazione

```bash
python3 -m unittest discover -s tests -v
python3 scripts/build_release.py
python3 scripts/install_local.py --project-root /percorso/progetto-interviste
```

L’installer locale usa lo stesso pacchetto e manifest dell’installer remoto.
Il progetto di destinazione può essere creato dall’installer. Non confondere
la presenza dei file con il riconoscimento osservato della skill in Codex.

Per provare il contratto contro il PHP effettivo, senza rete e con `mail()`
disabilitata, impostare `TRTALKS_BACKEND_SOURCE` al suo percorso e lanciare i test.
Questi test non provano l’invio o il backend remoto. Il test di duplicato
accettato usa uno stato server locale esplicitamente precompilato.

Per aggiungere una conversazione: [docs/SKILL-DI-CONVERSAZIONE.md](docs/SKILL-DI-CONVERSAZIONE.md).

Pubblicazione dal Terminale del computer di sviluppo:

```bash
python3 scripts/publish.py
```

La destinazione predefinita è `AgileReloaded/TRTalks`. Richiede Git e `gh`
autenticato con i permessi per creare/pubblicare il repository. Prima della
pubblicazione esegue i test; non invia email. `--dry-run` costruisce solo gli
asset e mostra il comando futuro di installazione senza usare Git o GitHub.

Procedura di pubblicazione: [docs/DISTRIBUZIONE.md](docs/DISTRIBUZIONE.md).
Prove iniziali conservate come cronologia: [docs/VERIFICA.md](docs/VERIFICA.md).
