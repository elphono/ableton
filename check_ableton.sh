#!/usr/bin/env bash
# Diagnostic de la chaine Claude Code (WSL) -> serveur MCP (Windows) -> Live.
# Chaque etage est teste separement : sans cela, une panne au dernier etage
# ressemble a une panne du premier.
set -uo pipefail

REPO_WIN='C:\Users\elphono\dev\ableton-mcp'
REPO='/mnt/c/Users/elphono/dev/ableton-mcp'
PY="$REPO/.venv/Scripts/python.exe"
SCRIPT_LIVE='/mnt/c/Users/elphono/Documents/Ableton/User Library/Remote Scripts/AbletonMCP/__init__.py'

ok()   { echo "  [ OK ]  $1"; }
fail() { echo "  [FAIL]  $1"; }

echo "1. Venv Windows"
[ -x "$PY" ] && ok "$REPO_WIN\\.venv" || { fail "venv introuvable"; exit 1; }

echo "2. Le serveur MCP s'importe"
if "$PY" -c "import MCP_Server.server" 2>/dev/null; then
  ok "MCP_Server.server"
else
  fail "import impossible — relancer : $PY -m pip install -e ."
fi

echo "3. Remote Script deploye dans la User Library"
if [ -f "$SCRIPT_LIVE" ]; then
  if diff -q "$REPO/AbletonMCP_Remote_Script/__init__.py" "$SCRIPT_LIVE" >/dev/null 2>&1; then
    ok "a jour"
  else
    fail "DIFFERENT du repo — redeployer puis recharger la Control Surface"
  fi
else
  fail "absent de la User Library"
fi

echo "4. Live repond sur 127.0.0.1:9877"
"$PY" - <<'PYEOF'
import socket, json
s = socket.socket(); s.settimeout(4)
try:
    s.connect(('localhost', 9877))
    s.sendall(json.dumps({'type': 'get_session_info', 'params': {}}).encode())
    data = json.loads(s.recv(65536).decode())
    r = data.get('result', {})
    print("  [ OK ]  Live repond : {0} pistes, {1} retours, {2:.2f} BPM".format(
        r.get('track_count', '?'), r.get('return_track_count', '?'), r.get('tempo', 0)))
except Exception as e:
    print("  [FAIL]  {0}".format(str(e)[:70]))
    print("          -> Live ouvert ? Options > Reglages (Ctrl+,) >")
    print("             onglet 'Tempo & MIDI' > Control Surface = AbletonMCP ?")
    print("          -> Script fraichement pose : redemarrer Live d'abord.")
PYEOF
