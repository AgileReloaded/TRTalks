# Contratto HTTP verificato nei sorgenti

Fonte: TRConversations/server, letta il 23 novembre 2026. Nessuna configurazione
privata è stata copiata. Il contenuto del server remoto non è stato verificato.

## Servizio di prova senza email

- URL: `https://techreloaded.it/shared/php/trdocument-http-test.php`.
- GET senza autenticazione: JSON `ok:true`, `status:"ready"`,
  `service:"trinterview-http-test"`, `email_sent:false`, `stored:false`.
- POST `Content-Type: application/json`, nessuna autenticazione. Unici campi:
  `request_id` con formato `probe-` seguito da 32 cifre esadecimali minuscole,
  `markdown` UTF-8 non vuoto, massimo 8192 byte; JSON massimo 65536 byte.
- Successo HTTP 200: `ok:true`, `status:"received"`, stesso `request_id`, stesso
  `markdown`, `bytes`, `sha256`, identità del servizio, `email_sent:false` e
  `stored:false`. Il client verifica tutti questi campi.
- Errori HTTP 400/405/413/415 con `ok:false` e `error`.
- Non salva né deduplica: `request_id` serve a correlare la risposta.
- Il PHP non include configurazioni, non scrive file e non chiama `mail()`.

## Backend operativo

`https://techreloaded.it/shared/php/trdocument-mcp.php` accetta soltanto POST
JSON-RPC 2.0. Non esiste in questo file una rotta POST REST che accetti i soli
campi del documento. Leggere un sorgente non prova quale versione sia online.

Il corpo previsto dal sorgente è un messaggio con `jsonrpc`, `id`,
`method:"tools/call"`, `params.name:"send-document"`, `params.arguments`:

| Campo arguments | Vincolo |
| --- | --- |
| request_id | 16–80 caratteri ASCII alfanumerici, `_` o `-` |
| approved | booleano true |
| name | non vuoto, massimo 200 byte, nessun carattere di controllo |
| filename | `[a-zA-Z0-9][a-zA-Z0-9_-]{0,100}.md` |
| markdown | UTF-8 non vuoto, massimo 262144 byte, senza NUL |
| email | facoltativa, Reply-To valido, massimo 254 byte |

L'autenticazione è disabilitata intenzionalmente nel sorgente. Le credenziali
non sono richieste a chi invia; il server usa configurazione privata e quote.

L'HTTP esterno può essere 200 anche per un errore applicativo. `result.content`
contiene JSON con `http_status` e `submission`; controllare anche `isError` e gli
errori JSON-RPC. `http_status:202` e `status:"accepted"` significano accettazione
da parte di `mail()` per la consegna, senza conferma di ricezione del destinatario.
Una ripetizione già accettata restituisce stato applicativo 200 e `duplicate:true`.

Il server lega l'ID al digest dell'intero payload; mantenerne esattamente campi,
valori e presenza nei ritentativi. Un conflitto di ID restituisce 409. Gli stati
pending/failed restituiscono `previous_attempt_requires_review`: non rigenerare
l'ID né riprovare automaticamente. Quote 3 nuovi invii/minuto e 20/24 ore; stato
di deduplicazione conservato per sei mesi. Non garantisce deduplicazione eterna.

`scripts/send_document.py` implementa questa POST senza configurare un client
MCP nell'app. Non occorrono nuove rotte PHP. Il controllo `status` chiama soltanto
`connection-status`; `send` è un'operazione distinta e richiede l'autorizzazione.

Il client congela documento, metadati, endpoint e ID prima della rete. Dopo un
timeout conserva lo stato incerto. Un ritentativo esplicito usa esclusivamente
il payload salvato. Non ritenta stati che richiedono revisione né tentativi più
vecchi di 150 giorni (margine conservativo rispetto alla conservazione server).
Un documento già accettato localmente restituisce la ricevuta senza reinvio.
`backend_accepted:true` viene emesso solo su ricevuta valida; negli esiti incerti
rimane `null`. `email_delivery:"unconfirmed"` non conferma l'arrivo di un'email.
