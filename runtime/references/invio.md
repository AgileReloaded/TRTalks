# Invio autorizzato del resoconto

Usare il launcher `trtalks` nella radice del progetto, con percorso assoluto.
In sviluppo: `python3 /percorso/TRTalks/runtime/trtalks.py --root /progetto ...`.
I comandi di invio vengono eseguiti dall'agente, non dall'intervistato.

## Configurazione

Leggere [backend.md](backend.md) per il funzionamento SMTP e i limiti dei retry.
Le credenziali sono in `.trtalks/config.local.json`, escluse dalla distribuzione.
Non stampare il file, non chiedere password nella chat e non inserirle negli
argomenti dei comandi. La configurazione iniziale della password avviene nel
terminale dell'utente con `trtalks init`, che chiede anche indirizzi, server,
porta, nome visualizzato e Reply-To e preserva le impostazioni preesistenti.
La procedura non invia email; non far inserire la password nella chat.

`trtalks configure --name 'Nome Cognome' --enable-send` imposta il nome e abilita
l'invio senza rete. Il JSON restituito mostra la destinazione effettiva senza
credenziali. Il destinatario iniziale è trtalks@techreloaded.it; quello di una
copia già configurata può essere diverso e va rispettato. `--recipient` permette
di cambiarlo su richiesta dell'utente. Non cambiare destinazione dopo l'approvazione.
Non richiedere una seconda autorizzazione del documento già approvato solo per
abilitare la configurazione locale. L'installazione non autorizza spedizioni.

`trtalks status` controlla TLS e autenticazione con NOOP, senza email.
`trtalks probe` crea soltanto un Markdown fittizio locale, senza rete.
Un test tecnico non autorizza un messaggio di prova: non chiamare `send`.

## Documento e autorizzazione

1. Salvare il Markdown finale UTF-8 con nome ASCII, lettere, numeri, `_` o `-`
   e suffisso `.md`. Mostrare il documento completo e il collegamento al file.
2. Esplicitare il destinatario effettivo, l'allegato e gli eventuali dettagli
   riservati. Raccogliere una sola autorizzazione a consegnare quella versione
   a quella destinazione. Il permesso di pubblicare un nome è distinto.
   Se l'autorizzazione è già stata data, usarla senza ripetere la domanda.
3. Eseguire `trtalks dry-run /percorso/intervista-nome.md` per ottenere SHA-256,
   destinatario e verifica del formato senza rete. Non equivale a un test SMTP.
4. Eseguire `trtalks send /percorso/intervista-nome.md --approved-sha256 HASH
   --authorization 'Riferimento alla decisione esplicita ricevuta in questa chat'`.
   Non inventare l'autorizzazione. Usare gli stessi byte mostrati e salvati.
   Quotare gli argomenti in modo sicuro, preferibilmente con subprocess e lista.

Se cambia il documento, mostrarlo nuovamente: l'approvazione precedente non
copre automaticamente modifiche del contenuto. Non alterare i byte per ottenere
un nuovo ID quando un invio è bloccato.

## Esiti

- `smtp_accepted:true`: «Il server SMTP ha accettato l'email con il documento
  allegato. La ricezione nella casella del destinatario non è confermata».
- `cached:true`: riutilizzata la ricevuta precedente; nessun nuovo invio.
- `failed_safe`: messaggio non accettato; correggere il problema e usare, se
  necessario, `trtalks retry REQUEST_ID` con identico messaggio e autorizzazione.
  Non chiedere nuovamente l'approvazione della medesima consegna.
- `uncertain`, `pending` o esito non determinato: conservare la bozza e lo stato;
  fermarsi e indicare che il reinvio richiede controllo manuale. SMTP non
  deduplica; non avviare retry, cicli o nuovi ID.

`.trtalks/deliveries/` conserva messaggio, ID, autorizzazione e ricevute private.
Non cancellarla durante update o uninstall. Non iniziare un invio se lo stato
non può essere salvato. Le vecchie ricevute HTTP restano conservate e non
possono essere ritentate attraverso il nuovo trasporto SMTP.
