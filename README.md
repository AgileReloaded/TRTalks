# TRTalks

Applicazione locale con più skill di conversazione per Codex, senza plugin
ChatGPT. **TRStory** raccoglie case histories e prepara resoconti Markdown.
La consegna avviene dal computer tramite SMTP cifrato, con allegato `.md`.
TRInterview/TRConversations e Websmith restano progetti separati e invariati.

Versione **0.4.0a2**: passaggio dal backend HTTP all'invio SMTP locale.
Il precedente script SMTP è stato provato dall'utente con esito positivo;
questo runtime è coperto da test locali. È previsto anche un test con server
SMTP TLS su loopback, saltato quando l’ambiente vieta socket locali (come nella
sessione di sviluppo corrente). Nessuna email esterna è stata inviata dal nuovo
runtime durante questa modifica. Il riconoscimento della skill e
la conversazione vocale nell'app effettiva richiedono una prova osservata.

## Installazione

Servono macOS/Linux, Python 3.9+, curl e l'app Codex autenticata. Nessun pip,
Node.js, Git o plugin ChatGPT richiesto a chi installa.

```bash
curl --proto '=https' --proto-redir '=https' -fsSL https://github.com/AgileReloaded/TRTalks/releases/latest/download/setup.sh | bash
```

Il comando installa **la release pubblicata**, non i sorgenti ancora da pubblicare.
Per scegliere una cartella diversa aggiungere `TRTALKS_HOME` davanti a `bash`:

```bash
curl --proto '=https' --proto-redir '=https' -fsSL https://github.com/AgileReloaded/TRTalks/releases/latest/download/setup.sh | TRTALKS_HOME="$HOME/TRTalks-prova" bash
```

L'installer verifica SHA-256 e manifest, crea il launcher `~/TRTalks/trtalks`,
installa il runtime in `.trtalks/app/` e le skill in `.agents/skills/ID/`.
Queste cartelle sono nascoste in Finder: `Cmd+Shift+.` le rende visibili.
Non sovrascrive skill estranee, configurazione o istruzioni di progetto.

Aprire `~/TRTalks` nell'app Codex e scrivere:

> Usa $trstory per raccogliere un caso TechReloaded.

`~/TRTalks/trtalks skills` elenca le tipologie disponibili; `paths` mostra i
percorsi. Ogni skill ha domande, regole e template propri; il runtime è comune.
La prima installazione lascia l'invio disabilitato e la password vuota.

## Configurazione SMTP, una volta per computer

```bash
~/TRTalks/trtalks init
~/TRTalks/trtalks status
```

La procedura chiede mittente, destinatario, nome visualizzato, server, porta,
username, Reply-To facoltativo e password nascosta. Premi Invio per accettare i
valori proposti. Su una copia già configurata propone le impostazioni esistenti
e permette di mantenere la password con Invio; conserva le altre chiavi locali.
Chiede se abilitare gli invii autorizzati e salva tutto soltanto alla fine,
nel file `.trtalks/config.local.json` con permessi **600**.
Non invia messaggi. `status` prova TLS, autenticazione e NOOP, senza email.
Non passare la password negli argomenti, non incollarla nella chat e non
stampare il file di configurazione. Il file contiene la password in chiaro
ed è escluso da Git, dai pacchetti e dagli aggiornamenti distribuiti.

| Impostazione | Valore iniziale |
| --- | --- |
| Server SMTP | mail.techreloaded.it |
| Porta | 465, TLS implicito con verifica del certificato |
| Username e mittente | trtalks@techreloaded.it |
| Destinatario | trtalks@techreloaded.it |
| Password | impostata localmente, mai inclusa nella release |

Il destinatario è configurabile, per esempio per la consegna alla redazione:

```bash
~/TRTalks/trtalks configure --recipient info@techreloaded.it
```

Altre opzioni: `--smtp-host`, `--smtp-port`, `--smtp-username`, `--smtp-from`,
`--email` (Reply-To), `--disable-send`. Le modifiche vengono validate prima del
salvataggio. Configurazione e verifiche non mostrano la password.

I colleghi configurano le credenziali sulla propria macchina: non vengono
scaricate dal repository. Nessuna chiamata HTTP al server MCP viene usata
per la consegna. La connessione HTTPS rimane per installazione e update.

## Intervista e consegna

L'assistente fa una domanda alla volta, adatta gli approfondimenti, accetta
correzioni, salti e conclusione. Non inventa dati e distingue risposte,
interpretazioni e lacune. Mostra il documento completo e rende disponibile
il file `.md`. La conversazione funziona anche in testo.

L'agente esplicita il destinatario effettivo e raccoglie una sola autorizzazione
alla consegna della versione finale, compresi eventuali dettagli riservati.
Se già ricevuta, non la richiede nuovamente. Poi esegue direttamente:

```text
trtalks dry-run /percorso/intervista-nome.md
trtalks send /percorso/intervista-nome.md --approved-sha256 HASH --authorization 'Riferimento alla decisione ricevuta'
```

L'intervistato non deve eseguire comandi di invio. `dry-run` verifica formato,
SHA-256 e destinatario senza rete. `probe` crea un Markdown fittizio locale,
anch'esso senza rete. Nessuna prova tecnica spedisce automaticamente email.

Prima della rete vengono salvati bozza autorizzata, messaggio MIME esatto,
Message-ID, request_id e autorizzazione in `.trtalks/deliveries/`. L'allegato
conserva i byte UTF-8 originali. Le credenziali non entrano nelle ricevute.
Il lock impedisce invii contemporanei nello stesso progetto.

- `smtp_accepted:true`: risposta SMTP 250 dopo DATA. Il server ha accettato
  l'email; la ricezione nella casella del destinatario resta **non confermata**.
- `cached:true`: ricevuta già accettata riutilizzata senza reinvio.
- `failed_safe`: errore prima di DATA o rifiuto esplicito. Dopo la correzione,
  `trtalks retry REQUEST_ID` riusa messaggio e autorizzazione salvati.
- `uncertain` o `pending`: reinvio bloccato. SMTP non deduplica tramite
  Message-ID; occorre un controllo manuale, senza nuovi ID o retry automatici.

Bozza e stato vengono conservati anche se l'invio fallisce. La deduplicazione
locale non copre altre installazioni o altri computer.

## Aggiornamento e disinstallazione

```bash
~/TRTalks/trtalks update --dry-run
~/TRTalks/trtalks update
~/TRTalks/trtalks uninstall
```

Gli update scaricano la release con checksum, provano l'avvio e sostituiscono
runtime e skill insieme, con rollback se una sostituzione fallisce. Non fanno
downgrade e preservano configurazione e credenziali, bozze, ricevute, `*.local.md`
e override. File gestiti modificati bloccano l'update invece di essere sovrascritti.
`uninstall` disattiva le skill e conserva documenti e impostazioni.

Le copie precedenti conservano integralmente la configurazione: il destinatario
può quindi essere ancora info@techreloaded.it. I nuovi campi SMTP vengono
integrati in memoria e scritti al successivo `init` o `configure`. Il vecchio campo
`endpoint`, se presente, viene ignorato. Le vecchie ricevute HTTP non vengono
convertite o ritentate via SMTP; un documento già registrato richiede revisione.
Non è necessario cancellare o reinstallare il progetto per passare a SMTP.

## Struttura e sviluppo

| Percorso | Scopo |
| --- | --- |
| `conversations.json` | Catalogo e lista dei file delle skill distribuite |
| `skills/trstory/` | Intervista, domande, regole e template TRStory |
| `runtime/trtalks.py` | CLI e configurazione locale |
| `runtime/send_document.py` | Autorizzazione, allegato, ricevute e retry sicuri |
| `runtime/delivery.py` | Trasporto SMTP TLS e verifica senza email |
| `runtime/manage.py` | Installazione, aggiornamenti e disinstallazione |
| `runtime/references/` | Istruzioni condivise di consegna e SMTP |
| `setup.sh` | Bootstrap HTTPS per i colleghi |
| `scripts/build_release.py` | ZIP deterministico con lista esplicita di file |
| `scripts/publish.py`, `scripts/draft_release.py` | Preparazione/pubblicazione GitHub |
| `scripts/test_smtp.py` | Test SMTP autonomo con password richiesta a ogni esecuzione |
| `docs/installazione.html` | Pagina di installazione |
| `tests/` | Trasporto, stato, TLS locale, configurazione e installazione |

```bash
python3 -m unittest discover -s tests -v
python3 scripts/build_release.py --release-url https://github.com/AgileReloaded/TRTalks/releases/latest/download
python3 scripts/install_local.py --project-root /percorso/progetto-interviste
```

In sviluppo usare `python3 runtime/trtalks.py --root /progetto COMANDO`.
Il runtime usa solo la libreria standard. Il test di integrazione TLS usa
`openssl` per un certificato temporaneo; non è una dipendenza dell'applicazione.

La release include solo i file dichiarati: nessuna configurazione, credenziale,
bozza o ricevuta locale. Pubblicare una nuova release per renderla disponibile
al comando `update`; il solo push dei sorgenti non aggiorna i colleghi.

Vedere [distribuzione](docs/DISTRIBUZIONE.md) e
[aggiunta di conversazioni](docs/SKILL-DI-CONVERSAZIONE.md).
I documenti `VERIFICA*.md` conservano le prove storiche della versione HTTP,
non descrivono il trasporto attuale.
