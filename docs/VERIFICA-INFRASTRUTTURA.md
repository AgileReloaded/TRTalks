> Documento storico della versione HTTP. Dalla 0.4.0a1 la consegna usa SMTP locale; vedere README.md.

# Verifica infrastruttura TRTalks — 23 novembre 2026

Documento storico della versione 0.2.0a1. La successiva separazione di TRStory
e del runtime comune è descritta in [SKILL-DI-CONVERSAZIONE.md](SKILL-DI-CONVERSAZIONE.md).

Versione preparata: **0.2.0a1**. Nessuna pubblicazione o email remota eseguita.
I progetti TRInterview/TRConversations e Websmith sono stati letti senza modificarli.

## Risultati osservati

| Area | Verifica | Esito |
| --- | --- | --- |
| Skill | Validatore locale ufficiale | `Skill is valid!` |
| Runtime | CLI sorgente `--version` | `0.2.0a1` |
| Bootstrap | `bash -n setup.sh` | Superato |
| Pacchetto | Costruzione deterministica, manifest e checksum | Superata |
| Installazione | Copia reale in progetti temporanei e avvio launcher | Superata |
| Update | Nuova versione, anteprima e rifiuto downgrade | Superati |
| Configurazione | Impostazioni e chiavi locali aggiuntive conservate | Superata |
| Dati | Bozze, stato e `*.local.md` conservati durante update | Superata |
| Errori update | Errore di scrittura provocato dal test, programma precedente ripristinato | Superata |
| Uninstall | Skill disattivata, altri skill e dati conservati | Superata |
| Client di consegna | Hash autorizzato, byte invariati, lock e riuso ID | Superati |
| Timeout e duplicati | Payload congelato, nessun secondo ID automatico | Superati |
| Risposte | Distinzione HTTP/JSON-RPC/submission e email non confermata | Superata |
| PHP effettivo | Tre test locali via CLI con `mail()` disabilitata | Superati |
| Totale suite | 29 test | Superati |

Log effettivo: `artifacts/tests-infrastructure.log`.

Il test di update remoto usa download sintetici dichiarati nel test, poi
installa realmente i file su filesystem temporaneo. Non dimostra un download
Internet. Gli altri test del client usano risposte sintetiche esplicite.

I test PHP caricano il sorgente effettivo indicato da `TRTALKS_BACKEND_SOURCE`.
Adattano solo `php://input` a stdin in memoria, senza modificare il sorgente.
`mail()` è disabilitata dal runtime PHP e sendmail è impostato a `/usr/bin/false`.
Il test positivo del duplicato usa uno stato locale `accepted` precompilato:
non è un’email inviata e non viene presentato come prova di consegna.
Un altro test lascia il PHP in pending dopo la chiamata disabilitata e verifica
che il ritentativo richieda revisione anziché un nuovo invio.

Comando eseguito:

```bash
TRTALKS_BACKEND_SOURCE=/Users/giovanni/progetti/TRConversations/server/trdocument-mcp.php python3 -m unittest discover -s tests -v
```

## Pacchetto effettivamente costruito

- Archivio: `dist/trtalks.zip`, 13 file inclusi manifest.
- Versione: `0.2.0a1`.
- SHA-256: `055fb0dd3f087e7dc61e1a3f5b927037da9b8d2d46ef744f849051c41cf4fc7b`.
- Asset aggiuntivi: `SHA256SUMS`, `release.json`, `setup.sh`, `index.html`.
- URL di distribuzione: non configurato. Il builder può inserirlo in setup e pagina.
- Credenziali, configurazione locale, bozze e stato consegne: esclusi dal pacchetto.

## Controlli remoti realmente tentati

`trtalks status` ha tentato una POST read-only `connection-status` a:

`https://techreloaded.it/shared/php/trdocument-mcp.php`

Esito reale:

```text
<urlopen error [Errno 8] nodename nor servname provided, or not known>
```

`delivery.py probe` ha tentato la GET preliminare a:

`https://techreloaded.it/shared/php/trdocument-http-test.php`

Esito: medesimo errore DNS. Nessuna POST di prova eseguita. Il documento
fittizio e il precedente ID di prova sono stati conservati e riutilizzati.

Il controllo read-only del repository proposto `techreloaded-ar/TRTalks` ha
restituito:

```text
error connecting to api.github.com
check your internet connection or https://githubstatus.com
```

Esiti grezzi: `artifacts/infrastructure-network-checks.json`.
Questi errori non dimostrano l’assenza del repository o un guasto del backend
fuori da questa sessione. Nessuna risposta remota è stata simulata.

## Da verificare dopo la pubblicazione

Installazione completa da HTTPS su un computer reale, download di una seconda
release e update online, riconoscimento e intervista nell’app Codex, voce e
consegna email autorizzata. La bozza può essere consegnata solo dopo una
richiesta esplicita: nessun invio `send-document` è stato tentato via rete.

La scrittura in `.agents` e `.git` del progetto di sviluppo è risultata negata
nella prima prova e non è stata aggirata. I test di installazione di questa
fase usano esclusivamente cartelle temporanee isolate: non equivalgono a una
skill attivata nell’app di Giovanni. I sorgenti non sono ancora registrati in Git.

Pubblicazione e pagina pubblica restano da completare dopo aver definito la
destinazione e ottenuto connettività. Procedura in `DISTRIBUZIONE.md`.
