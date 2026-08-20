#!/usr/bin/env python3
"""Parler directement au Remote Script, sans passer par le serveur MCP.

Sert a deux choses :

1. **Diagnostiquer.** Quand un tool MCP echoue, cet outil dit lequel des deux
   etages est en cause. Si la commande brute passe et que le tool MCP echoue,
   le bug est dans `MCP_Server/server.py` ; sinon il est dans le Remote Script.
2. **Atteindre ce que le serveur MCP n'expose pas.** Les signatures des tools
   sont des listes fermees de parametres : une propriete acceptee par la liste
   blanche du Remote Script mais absente de la signature du tool est
   injoignable autrement.

Le protocole est du JSON sur TCP 127.0.0.1:9877, une requete par connexion :

    {"type": "<commande>", "params": {...}}

Usage :
    python3 ableton_raw.py get_session_info
    python3 ableton_raw.py set_arrangement_clip_property \\
        track_index=4 clip_index=0 property=end_marker value=8.0
    python3 ableton_raw.py inspect_lom path='tracks[0]'

Les valeurs sont converties : `12` -> int, `1.5` -> float, `true`/`false` ->
bool, `null` -> None, le reste reste une chaine. Prefixer par `:` force la
chaine (`name=:12` envoie "12").

ATTENTION aux index : les commandes du Remote Script sont **0-based** (c'est le
serveur MCP qui offre le 1-based a l'utilisateur). Ici on parle au Remote
Script : `track_index=0` est la premiere piste.

Le Remote Script ecoute sur le `localhost` **de Windows** (bind explicite sur
"localhost", pas sur 0.0.0.0) : depuis WSL la connexion est refusee, l'IP de
l'hote ne sert a rien. Ce script s'en sort seul — il se rejoue via le Python
Windows en se passant son propre source sur stdin. Pas de copie a garder
synchronisee, et surtout pas de chemin \\\\wsl.localhost\\... donne a un
binaire Windows, ce qui echoue ou ment.
"""
import json
import os
import socket
import subprocess
import sys

HOST, PORT = "127.0.0.1", 9877
TIMEOUT = 15.0
WIN_PYTHON = "/mnt/c/Users/elphono/dev/ableton-mcp/.venv/Scripts/python.exe"


def coerce(text):
    """Deviner le type d'une valeur de ligne de commande."""
    if text.startswith(":"):
        return text[1:]
    low = text.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    if low == "null" or low == "none":
        return None
    for cast in (int, float):
        try:
            return cast(text)
        except ValueError:
            pass
    if text[:1] in "[{":
        try:
            return json.loads(text)
        except ValueError:
            pass
    return text


def send(command, params):
    """Envoyer une commande et rendre la reponse decodee.

    Le Remote Script peut repondre en plusieurs paquets TCP : on lit jusqu'a ce
    que le JSON soit complet, sinon un gros `inspect_lom` arrive tronque.
    """
    sock = socket.socket()
    sock.settimeout(TIMEOUT)
    sock.connect((HOST, PORT))
    try:
        sock.sendall(json.dumps({"type": command, "params": params}).encode("utf-8"))
        chunks = b""
        while True:
            chunk = sock.recv(65536)
            if not chunk:
                break
            chunks += chunk
            try:
                return json.loads(chunks.decode("utf-8"))
            except ValueError:
                continue
        raise RuntimeError("reponse tronquee ou vide")
    finally:
        sock.close()


def relay_through_windows():
    """Rejouer ce script sous le Python Windows, source passe sur stdin.

    N'est tente qu'apres un refus de connexion : si un jour l'hote joint Live
    directement, le chemin normal continue de marcher sans detour.
    """
    if not os.path.exists(WIN_PYTHON):
        return None
    with open(__file__, "rb") as handle:
        source = handle.read()
    done = subprocess.run(
        [WIN_PYTHON, "-X", "utf8", "-"] + sys.argv[1:],
        input=source, capture_output=True,
    )
    sys.stdout.write(done.stdout.decode("utf-8", "replace"))
    sys.stderr.write(done.stderr.decode("utf-8", "replace"))
    return done.returncode


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    command = sys.argv[1]
    params = {}
    for arg in sys.argv[2:]:
        if "=" not in arg:
            print("Argument ignore (pas de '=') : {0}".format(arg), file=sys.stderr)
            continue
        key, _, value = arg.partition("=")
        params[key] = coerce(value)

    try:
        reply = send(command, params)
    except ConnectionRefusedError:
        relayed = relay_through_windows()
        if relayed is not None:
            return relayed
        print("ECHEC : connexion refusee sur {0}:{1}".format(HOST, PORT), file=sys.stderr)
        print("  -> Live ouvert ? Control Surface AbletonMCP active ?", file=sys.stderr)
        return 2
    except Exception as e:
        print("ECHEC {0} : {1}".format(type(e).__name__, e), file=sys.stderr)
        print("  -> Live ouvert ? Control Surface AbletonMCP active ?", file=sys.stderr)
        return 2

    print(json.dumps(reply, indent=2, ensure_ascii=False))
    return 0 if reply.get("status") == "success" else 3


if __name__ == "__main__":
    sys.exit(main())
