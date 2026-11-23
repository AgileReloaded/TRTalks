> Documento storico della versione HTTP. Dalla 0.4.0a1 la consegna usa SMTP locale; vedere README.md.

# Prima verifica TRTalks — 23 novembre 2026

Documento storico della prima prova. Per l’infrastruttura successivamente
implementata leggere [VERIFICA-INFRASTRUTTURA.md](VERIFICA-INFRASTRUTTURA.md).

## Risultati osservati

| Verifica | Esito | Evidenza |
| --- | --- | --- |
| Sorgenti del progetto corrente | Cartella inizialmente vuota | Elenco iniziale di TRTalks |
| Materiale TRInterview | Archivio ZIP letto, protocollo disponibile | `TRConversations/plugin/TRInterview.zip`, skill `instructions` |
| Contratto backend | Letti i PHP effettivi | `references/backend.md` |
| Installer Websmith | Letto script reale e implementazione init | `websmith-cli/setup.sh`, `src/websmith/initialize.py`, README |
| Dipendenze script | Python 3.9.6 disponibile | Esecuzione locale senza installare pacchetti |
| Struttura skill | Validatore ufficiale locale: `Skill is valid!` | `quick_validate.py skills/trtalks` |
| Test locali del client | 6 test superati | `python3 -m unittest discover -s tests -v` |
| Sintassi PHP di prova | Nessun errore | `php -n -l` sul sorgente esistente |
| Documento Markdown fittizio | Creato realmente e conservato | `artifacts/prova-http.md` |
| Installazione locale | Bloccata dalla sandbox | `[Errno 1] Operation not permitted: '/Users/giovanni/progetti/TRTalks/.agents'` |
| Codex riconosce e usa la skill installata | Non verificato | Installazione non riuscita; non è stato avviato un altro agente per simulare la prova |
| Breve scambio nell'app | Non eseguito | Nessuna risposta di intervista inventata |
| GET remota | Fallita prima di ottenere risposta HTTP | Errore DNS, sotto |
| POST remota | Non eseguita | Il preflight GET fallito impedisce la POST |
| HTTP locale con PHP | Non eseguito | Bind loopback negato: `PermissionError(1, 'Operation not permitted')` |
| Voce nell'app | Non verificata | Nessuna prova vocale reale |
| Registrazione sorgenti in Git | Bloccata dalla sandbox | `TRTalks/.git: Operation not permitted` da `git init` |

## Errore remoto reale

Lo script TRTalks è stato eseguito con `probe`, dopo aver creato il documento
fittizio e salvato il request_id. La GET preliminare ha restituito:

```text
<urlopen error [Errno 8] nodename nor servname provided, or not known>
```

Endpoint esatto:
`https://techreloaded.it/shared/php/trdocument-http-test.php`.

`curl` sul medesimo URL ha restituito:

```text
curl: (6) Could not resolve host: techreloaded.it
```

Ricevuta locale effettiva:
`artifacts/http-attempt-fbd12b9f27c24acc8eb4e0e519bdc4e0.json`.
Non esiste una risposta JSON del backend da mostrare. La ricevuta è l'esito del
client, non un risultato simulato del server. Il fallimento non prova che il
dominio o il servizio siano indisponibili fuori dalla sandbox.

Il PHP di prova letto non invia email. TRTalks non ha chiamato il backend
operativo né altri servizi di consegna. Nessuna email inviata da questa prova.

## Limiti e prosecuzione

I test automatici usano dati sintetici per verificare il parser della risposta,
la conservazione del documento e il riuso dell'ID: non sono risposte reali HTTP.
Non dimostrano funzionamento nell'app, backend remoto o voce.

Prima di proseguire con consegna reale e distribuzione occorre consentire
l'installazione nel percorso supportato e la connettività al servizio di prova.
Non sono stati aggirati i divieti della sandbox. Non è stata chiesta una seconda
autorizzazione a inviare: l'invio di email non fa parte di questa verifica.

TRConversations, TRInterview e Websmith sono stati letti senza modificarli.
