# Invio autorizzato del resoconto

Eseguire gli strumenti condivisi dell’applicazione TRTalks, con percorsi assoluti.
Il launcher installato è `trtalks` nella radice del progetto. In sviluppo usare
`python3 /percorso/TRTalks/runtime/trtalks.py --root /progetto ...`.
Gli esempi non sono comandi da chiedere all'intervistato: li esegue l'agente.

## Configurazione e controllo

`.trtalks/config.local.json` del progetto contiene nome mittente, Reply-To
facoltativo, endpoint e `send_enabled`. Non distribuire credenziali. Il backend
letto non richiede autenticazione né un account Gmail dell'intervistato.

Il comando `trtalks configure --name 'Nome Cognome' --enable-send` salva le
impostazioni senza rete. L'abilitazione va fatta su richiesta di configurazione
o quando l'utente autorizza esplicitamente l'invio; non fa parte delle prove
senza email. Non richiedere una nuova approvazione dello stesso documento solo
perché occorre impostare un nome o abilitare la configurazione locale.

`trtalks status` controlla il backend operativo senza email.
`trtalks probe` crea e trasmette solo il Markdown fisso di prova.
Gli errori di rete vanno riportati come osservati, senza cambiare endpoint.

## Documento e autorizzazione

1. Salvare il Markdown finale UTF-8; usare un nome ASCII con lettere, numeri,
   `_` o `-` e suffisso `.md`. Mostrare tutto il contenuto e il collegamento al
   file. Non modificare il documento dopo la sua autorizzazione.
2. Esplicitare la destinazione `info@techreloaded.it` e la presenza di eventuali
   dettagli riservati alla redazione. Raccogliere una sola autorizzazione alla
   consegna della versione finale. Il consenso a pubblicare un nome non basta.
   Rispettare l'autorizzazione già data alla consegna finale senza ripeterla.
3. Eseguire `trtalks dry-run /percorso/intervista-nome.md` per verificare formato,
   nome mittente e SHA-256, senza rete. Questo non equivale a un test del server.
4. Eseguire `trtalks send /percorso/intervista-nome.md --approved-sha256 HASH
   --authorization 'Autorizzazione esplicita ricevuta in questa chat per la versione finale'`.
   Il valore HASH viene dalla verifica dei byte effettivamente mostrati e salvati.
   Non assegnare un'autorizzazione se manca. Quotare gli argomenti in modo sicuro;
   preferire un elenco di argomenti di subprocess se il testo contiene metacaratteri.

Se dopo l'autorizzazione vengono richieste modifiche, aggiornare e mostrare il
documento. L'autorizzazione alla versione precedente non copre automaticamente
modifiche successive che cambiano il contenuto. Non cambiare i byte per sistemare
un problema di rete o per ottenere un nuovo ID.

## Esiti e ritentativi

- `backend_accepted:true`: «Il backend ha accettato il documento per la consegna;
  la ricezione dell'email non è confermata». Non scrivere «email ricevuta».
- `cached:true`: una ricevuta precedente già accettata è stata riutilizzata;
  nessuna nuova richiesta di invio è stata eseguita.
- `local_status:"uncertain"` o errore di rete: conservare bozza e stato e indicare
  l'esito non determinato. Non generare un nuovo ID. Un eventuale ritentativo
  richiesto o appropriato usa `trtalks retry REQUEST_ID`, una volta, senza chiedere
  di nuovo l'approvazione del medesimo payload. Non avviare un ciclo di retry.
- `review_required`: fermarsi; il backend richiede un controllo. Non rigenerare
  l'ID e non aggirare il blocco rinominando il file.

La directory privata `.trtalks/deliveries` conserva payload congelato, ID,
autorizzazione e ricevute. Non cancellarla durante update/uninstall e non
includerla nel pacchetto. Il lock locale impedisce tentativi contemporanei.
Se lo stato non può essere salvato, non iniziare un nuovo invio.
