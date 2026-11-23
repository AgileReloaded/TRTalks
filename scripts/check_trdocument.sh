#!/usr/bin/env bash
# One read-only HTTP POST to the existing TechReloaded backend. No email send.
set -euo pipefail

case "${1:-}" in
  -h|--help)
    printf '%s\n' \
      'Uso: bash scripts/check_trdocument.sh' \
      'Esegue solo connection-status su trdocument-mcp.php.' \
      'Mostra URL, richiesta, header, corpo e codice HTTP. Non invia email.'
    exit 0
    ;;
  '') ;;
  *) printf '%s\n' 'Argomento non riconosciuto. Usa --help.' >&2; exit 2 ;;
esac
if [ "$#" -gt 1 ]; then
  printf '%s\n' 'Questo script non richiede argomenti.' >&2
  exit 2
fi
command -v curl >/dev/null || { printf '%s\n' 'Serve curl.' >&2; exit 1; }

trtalks_endpoint='https://techreloaded.it/shared/php/trdocument-mcp.php'
trtalks_payload='{"jsonrpc":"2.0","id":"trtalks-diagnostic-status","method":"tools/call","params":{"name":"connection-status","arguments":{}}}'
# Same explicit identity used by the current TRTalks HTTP client.
trtalks_user_agent='TRTalks/0.2'

printf 'URL: %s\nUser-Agent: %s\nOperazione: connection-status (nessun invio email)\n' \
  "$trtalks_endpoint" "$trtalks_user_agent"
printf 'Richiesta JSON:\n%s\n\nRisposta HTTP completa:\n' "$trtalks_payload"

# No redirects, browser cookies, retries or certificate-validation exceptions.
# Do not use --fail: the error response body is needed for diagnosis too.
curl --silent --show-error --include \
  --proto '=https' \
  --connect-timeout 10 --max-time 30 \
  --request POST \
  --header 'Accept: application/json' \
  --header 'Content-Type: application/json; charset=utf-8' \
  --user-agent "$trtalks_user_agent" \
  --data-binary "$trtalks_payload" \
  --write-out '\n\nCodice HTTP: %{http_code}\nContent-Type: %{content_type}\n' \
  "$trtalks_endpoint"
