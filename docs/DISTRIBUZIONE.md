# Preparazione della distribuzione

## Destinazione di pubblicazione

Il modello è una release di repository pubblico, come Websmith. L’utente ha
creato su GitHub il repository pubblico `AgileReloaded/TRTalks` e ha configurato
in Fork `origin` come `https://github.com/AgileReloaded/TRTalks.git`.
La release installabile non è ancora pubblicata e verificata. La rete di
questa sessione non raggiunge GitHub. `AgileReloaded/TRTalks` è la destinazione predefinita del comando
`python3 scripts/publish.py`, predisposto per eseguire dal Terminale creazione
del repository pubblico, commit dei sorgenti, push, tag e pubblicazione degli asset.
La sessione corrente non ha eseguito tali operazioni remote.

È possibile anche usare un host HTTPS statico: servono nella medesima directory
`setup.sh`, `trtalks.zip`, `SHA256SUMS` e, per le istruzioni, `index.html`.
L’URL configurato indica la directory, non il singolo ZIP. Non richiede un sito
dinamico o nuove rotte del backend email.

## Costruzione e prima pubblicazione GitHub manuale (alternativa al comando publish)

1. Scegliere o creare il repository pubblico e registrarne l’URL. Versionare i
   sorgenti ed escludere i dati locali tramite `.gitignore`. Il pacchetto usa
   una lista esplicita dei file e non include nemmeno file estranei alla lista.
2. Eseguire i test, aggiornare `VERSION` e creare/pushare il tag corrispondente.
   La release iniziale predisposta è `0.3.0a1`, tag `v0.3.0a1`.
3. Generare gli asset con la base download reale:

   ```bash
   python3 scripts/build_release.py --release-url https://github.com/OWNER/REPO/releases/latest/download
   ```

   Questo inserisce la base in `dist/setup.sh` e `dist/index.html`. Senza il
   parametro il pacchetto è comunque costruito ma il bootstrap richiede
   `TRTALKS_RELEASE_URL` e la pagina segnala che l’URL non è configurato.
4. Per caricare una release di prova sul tag già presente:

   ```bash
   python3 scripts/draft_release.py --repo OWNER/REPO
   ```

   Richiede `gh` autenticato al distributore, non ai colleghi. Usa `--draft`
   e `--verify-tag`: non crea repository, non crea tag remoti e non pubblica.
   Rifiuta la mancanza del tag. Non sovrascrive una release già esistente.
5. Verificare gli asset e pubblicare la bozza, quando si intende renderla
   scaricabile. La base `latest/download` richiede una release pubblicata e
   contrassegnata come Latest, anche se il numero ha suffisso alpha:

   ```bash
   gh release edit v0.3.0a1 --repo OWNER/REPO --draft=false --latest
   ```

6. Ospitare `dist/index.html` come pagina pubblica (per esempio GitHub Pages o
   SiteGround) e dare quel link ai colleghi. Un asset HTML di una release può
   essere scaricato invece di essere visualizzato come sito: non basta caricarlo
   come allegato per avere la pagina di istruzioni online.

Le operazioni remote non sono state eseguite da questa sessione. Per costruire
una versione fissata usare come base `/releases/download/vVERSION` anziché
`/releases/latest/download`; l’updater resta su quella base finché non riceve
`--release-url` con una nuova sorgente.

## Collaudo prima di distribuire ai colleghi

- Installare dalla release pubblica senza autenticazione GitHub in una cartella
  dedicata e controllare versione e presenza della skill nell’app effettiva.
- Eseguire una breve intervista testuale fittizia e controllare il Markdown.
- Eseguire `probe` e controllare la risposta reale senza email. Non sostituire
  questo test con un invio al backend operativo.
- Eseguire `status` sul backend operativo: questo non spedisce.
- Provare una seconda release con `update`, verificando che configurazione,
  bozze, eventuali credenziali e ID di consegna restino identici.
- Verificare la voce separatamente: dettatura e dialogo vocale non equivalgono.
- La verifica di invio email richiede una richiesta esplicita distinta. Non è
  stata eseguita durante la preparazione dell’infrastruttura.

## Configurazione locale

Il setup inizializza `send_enabled:false`. Il backend letto non richiede token;
se in futuro verrà introdotta autenticazione, dovrà stare nella configurazione
o nell’ambiente locale ed essere supportata dal contratto server prima dell’uso.
Non distribuire un segreto condiviso nelle skill.

Nessuno script scrive nei progetti TRInterview/TRConversations o Websmith.
L’updater non esegue pull Git, non tocca il repository dei sorgenti e non
modifica le impostazioni di sicurezza dell’app Codex.
