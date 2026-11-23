# Trasporto SMTP locale

TRTalks invia direttamente dal computer al server SMTP, senza chiamare endpoint
HTTP, MCP, plugin ChatGPT o Gmail. HTTP resta soltanto per scaricare gli aggiornamenti.

## Configurazione

Il file privato del progetto `.trtalks/config.local.json` contiene:

| Campo | Valore iniziale |
| --- | --- |
| transport | smtp |
| smtp_host | mail.techreloaded.it |
| smtp_port | 465 |
| smtp_username | trtalks@techreloaded.it |
| smtp_password | vuota; da configurare localmente |
| smtp_from | trtalks@techreloaded.it |
| recipient | trtalks@techreloaded.it |
| sender_name | nome della persona che consegna il resoconto |
| reply_to | facoltativo |
| send_enabled | false |

Il destinatario è configurabile. Le installazioni precedenti mantengono il loro
destinatario, per esempio info@techreloaded.it: leggere quello effettivo prima
dell'autorizzazione. Un eventuale vecchio campo `endpoint` viene conservato per
non perdere configurazione locale, ma non viene usato.

Si usa esclusivamente SMTP con TLS implicito e verifica del certificato,
normalmente sulla porta 465. Non vengono disabilitati i controlli TLS.
La configurazione viene scritta atomicamente con permessi 600. Se contiene una
password ed è accessibile ad altri utenti, il runtime chiede di correggere i
permessi prima di leggerla per l'invio. Password in chiaro nel file locale per
scelta di configurazione: non stamparla, non copiarla nella chat, nei log, nelle
ricevute, nelle skill o nel pacchetto. Non leggerla con strumenti che mostrano
l'intero file. Usare `trtalks init` nel terminale per la configurazione guidata completa,
oppure `configure --smtp-password` per cambiare soltanto la password.

## Operazioni ed esiti

`status` apre una connessione TLS, esegue l'autenticazione e NOOP. Non invia
MAIL, RCPT o DATA e non spedisce email. Una verifica riuscita non prova l'arrivo
di un'email. `probe` crea esclusivamente un documento fittizio locale senza rete.

`send` salva documento, metadati, autorizzazione, Message-ID e messaggio MIME
completo prima della rete. Spedisce una email con allegato `.md`: la codifica
base64 conserva i byte UTF-8 autorizzati, comprese le terminazioni di riga.
Il nome della persona compare nel mittente visualizzato; `smtp_from` resta
l'indirizzo della casella autorizzata. `reply_to`, se presente, diventa Reply-To.
Username e password non vengono inseriti nel messaggio; la password resta
esclusivamente nella configurazione locale.

`smtp_accepted:true` richiede la risposta SMTP 250 dopo DATA. Significa soltanto
che il server ha accettato il messaggio; `email_delivery:"unconfirmed"` non
conferma la ricezione nella casella destinataria. Nessuna logica dipende da
`backend_accepted`, risposte HTTP o JSON-RPC.

## Ritentativi e migrazione

SMTP non offre una chiave di idempotenza. Message-ID e request_id stabili servono
alla tracciabilità, non garantiscono che il server elimini i duplicati.

- `accepted`: riusare la ricevuta locale, senza connessione o reinvio.
- `failed_safe`: errore prima di DATA o rifiuto esplicito del messaggio. Un retry
  può riusare lo stesso ID e gli stessi byte dopo la correzione del problema.
- `uncertain` o `pending`: reinvio bloccato, anche con `retry`; occorre verificare
  manualmente lo stato dell'email. Non cancellare lo stato e non creare un altro
  ID o modificare il documento per aggirare il blocco.

La password può essere corretta tra due tentativi sicuri; server, account,
mittente e destinatario devono restare gli stessi. Le vecchie ricevute HTTP
vengono conservate: non sono convertite in tentativi SMTP. Un documento già
registrato nel vecchio flusso richiede revisione manuale prima di un altro invio.
Il lock locale protegge da invii paralleli sullo stesso progetto; non deduplica
fra computer o installazioni differenti.
