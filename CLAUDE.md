# live-sidekick — piloter Ableton Live 12 depuis Claude Code

Outillage autour d'un serveur MCP `ableton` : fork maison de
[uisato/ableton-mcp-extended](https://github.com/uisato/ableton-mcp-extended).
Ce dépôt porte les outils locaux et le savoir **mesuré** sur le Live Object Model ;
le fork du serveur vit dans un checkout séparé (voir plus bas).

**Politique de langue de ce dépôt** : `README.md` en anglais (dépôt public),
`CLAUDE.md` en français, code et tests en anglais pour toute écriture nouvelle.
Le code existant est en français ASCII et n'est pas retraduit rétroactivement.

## Où vivent les choses

| Quoi | Où | Variable qui le surcharge |
|---|---|---|
| Checkout du serveur MCP (fork) | `%USERPROFILE%\dev\ableton-mcp` | `ABLETON_MCP_DIR` (chemin WSL) |
| Venv Windows du serveur | `<checkout>\.venv` (Python 3.11) | `ABLETON_MCP_PYTHON` |
| User Library d'Ableton | `%USERPROFILE%\Documents\Ableton\User Library` | `ABLETON_USER_LIBRARY` (chemin WSL) |
| Remote Script chargé par Live | `<User Library>\Remote Scripts\AbletonMCP\__init__.py` | — |
| Venv WSL des outils et des tests | `.venv/` de ce dépôt (numpy, pytest) | — |
| ffmpeg / ffprobe | Windows uniquement, dans le PATH (`ffmpeg.exe`) | — |

Les défauts sont calculés depuis `%USERPROFILE%` (via `cmd.exe` + `wslpath`) : rien
n'est câblé en dur sur une machine.

**Le Remote Script est une copie**, pas un lien. Après toute modification dans le
checkout, le redéployer :

```bash
cp "$ABLETON_MCP_DIR/AbletonMCP_Remote_Script/__init__.py" \
   "$ABLETON_USER_LIBRARY/Remote Scripts/AbletonMCP/__init__.py"
```

…puis **redémarrer Live**. Basculer la Control Surface sur *None* puis de nouveau
sur *AbletonMCP* ne recharge PAS un script modifié (vérifié 2026-08-16) : Live garde
le module dans `sys.modules`, et l'ancienne version continue de répondre
normalement. En cas de doute, appeler un handler qui n'existe que dans la nouvelle
version (`./check_ableton.sh` compare aussi le fichier déployé au checkout).

### Où se trouve le réglage (Live 12.4)

**Options → Réglages…** (Ctrl + ,) → onglet **« Tempo & MIDI »** → section
**Control Surface** → *AbletonMCP*. Live 12.4 a scindé l'onglet « Link, Tempo &
MIDI » du manuel en deux : c'est le second. Laisser **Entrée** et **Sortie** sur
*Aucune* : le script ouvre un socket TCP, il ne passe pas par le MIDI.

## Architecture

```
Claude Code (WSL2) --stdio--> cmd.exe /c run_server.bat (Windows)
                                  └─ serveur MCP Python --TCP 9877--> Remote Script dans Live
```

Tout ce qui est Windows reste Windows. Le TCP est du pur `localhost` Windows : pas
de bind `0.0.0.0`, pas de règle de pare-feu, pas d'IP d'hôte WSL.

## Pièges vérifiés

| Piège | Ce qu'il faut faire |
|---|---|
| Les variables d'environnement **ne franchissent pas** l'interop WSL→Windows | Les poser dans `run_server.bat`, pas côté WSL |
| Console Windows en cp1252 : tout nom de piste accentué lève `UnicodeEncodeError` | `run_server.bat` force `-X utf8` + `PYTHONUTF8=1` |
| `cmd.exe` lancé depuis un cwd WSL écrit un avertissement UNC sur stderr, dans la page de code console (pas UTF-8) | Lancer depuis `/mnt/c`, ignorer stderr |
| Un process Windows qui lit un chemin `\\wsl.localhost\...` plante ou rend faux | **Tous les médias sur un disque Windows**, jamais sous `/home` — `preparer_extrait.py` refuse |
| MCP SDK 2.x a retiré `mcp.server.fastmcp` | Épingler `mcp[cli]<2` |
| `pyproject.toml` amont déclare `AbletonMCP_UDP`, qui n'existe pas | Retiré du fork |
| Live n'expose **aucune API d'export audio** dans le LOM | Export final à la main (Ctrl + Maj + R) |

## Extensions maison du fork

Ajoutées des deux côtés (Remote Script + serveur MCP) :

- `create_audio_track`, `create_return_track` — l'amont n'avait que des pistes MIDI
- `set_track_state` — mute / solo / arm ; `get_sends` / `set_send` — effets en bus
- `get_mixer_info` — instantané complet du mixer en un appel
- `inspect_lom` — **introspection du Live Object Model à l'exécution**
- `get_clip_notes`, `remove_clip_notes`, `delete_session_clip` — l'amont ne savait
  qu'**ajouter** des notes : sans relecture ni suppression, pas de boucle de travail
- `measure_arrangement_clip` — mesurer l'étirement d'un clip **déjà posé** (voir
  « second aller-retour » plus bas)

Corrigés parce qu'ils mentaient :

- `create_arrangement_audio_clip` prend `warp` et renvoie l'étirement constaté. Il
  mesurait dans le tick où il venait d'écrire `warping`, donc sur l'étendue
  d'avant : un WAV de 6,000 s posé avec `warp=False` était annoncé « +33,33 % ».
  La mesure se fait maintenant dans un **second aller-retour**.
- `set_arrangement_clip_property` renvoie les **conséquences observables** et
  signale les propriétés inertes.
- `set_clip_fade` cherchait « Volume » quand Live dit « Track Volume », et rampait
  vers `param.max` = **+6 dB** au lieu du niveau nominal.
- `manage_clip_automation` visait un clip d'arrangement : il ne pouvait **jamais**
  aboutir. Il vise les slots de session.
- `load_instrument_or_effect` annonçait « Devices on track: » suivi de rien.

**Convention d'index des outils maison** : `1..n` = pistes, `n+1..n+r` = retours,
**`0` = master**. (Les outils amont sont 1-based sans master ; le Remote Script brut,
lui, est 0-based.)

**Ne jamais mesurer une conséquence dans le tick qui vient de l'écrire.** Après
`clip.warping = False`, `warping` se relit juste mais `length`, `start_time` et
`end_time` décrivent encore l'import warpé ; une seule relecture ultérieure suffit
à les stabiliser. La relecture doit être un aller-retour distinct.

## Outils locaux

| Outil | Rôle |
|---|---|
| `check_ableton.sh` | diagnostic des 4 étages de la chaîne |
| `ableton_raw.py` | parler **directement** au Remote Script — isole une panne du serveur MCP, et atteint ce que les signatures des tools n'exposent pas |
| `preparer_extrait.py` | découper un extrait, fondus cuits dedans, en WAV prêt à poser — **refuse** tout écart > 2 échantillons |
| `analyse_audio.py` | tempo (interpolé sous la trame, ±1 BPM) et tonalité d'un extrait |
| `wsl_paths.py` | traduction `/mnt/x/…` → `X:\…` partagée par les outils ffmpeg |
| `tests/` | `.venv/bin/python -m pytest` |

`ableton_raw.py` reste **autonome** (aucun import local) : il se rejoue sous le
Python Windows en se passant son propre source sur stdin.

## Ce que le LOM de Live 12.4.3 expose vraiment (mesuré, pas supposé)

Des propriétés *présentes* et *acceptées* ne sont pas pour autant *utiles* : la
première version de ce tableau l'avait confondu.

| Sur un clip d'arrangement | État réel |
|---|---|
| `end_marker` | accepté, relu, **`length` inchangé** → ne rogne rien |
| `start_marker` | **remis à `0.0` en silence** |
| `position` | déplace la **boucle dans le sample**, pas le clip |
| `loop_start` / `loop_end` + `looping` | agissent, mais font **boucler**, ne raccourcissent pas |
| `start_time`, `end_time` | **lecture seule** → un clip ne se déplace pas |
| `fade_in_length`, `fade_out_length` | absents |
| `create_automation_envelope` | **refusé** : « Not a session clip » |
| Écriture d'automation d'arrangement | **inexistante** (`automation_state` en lecture seule) |
| Toute méthode d'export / render / bounce | **aucune** |
| `Track.create_audio_clip(path, position)` | présent → seule voie pour poser un fichier |
| Le master | lève une exception à la lecture de `.mute` ; `getattr(..., défaut)` ne l'attrape pas |

**Conséquence** : Live assemble, il ne monte pas. Les extraits arrivent déjà coupés
et déjà fondus (`preparer_extrait.py`). Un crossfade se construit en superposant
deux extraits sur **deux pistes**, chacun portant son fondu dans son fichier.

**`inspect_lom` d'abord, deviner jamais** : l'API Python de Live change d'une version
à l'autre et la documentation est en retard.

```
inspect_lom("tracks[0].arrangement_clips[0]")
```

### Les deux distorsions temporelles qui cassent un calage

Mesurées, cumulatives, silencieuses :

1. **Live warpe tout import** : 15,000 s → 16,000 s (**+6,1 %**). Poser avec `warp=False`.
2. **Un mp3 ne commence pas au même endroit dans Live et dans ffmpeg** : **84,6 ms**
   d'écart (2,5 images à 29,97 fps) — le silence d'amorce LAME, que ffmpeg retire
   et que Live joue. En WAV l'écart tombe à **0 échantillon**. Donc **jamais de mp3
   dans Live**.

## Diagnostic

```bash
./check_ableton.sh                       # les 4 étages, testés séparément
python3 ableton_raw.py get_session_info  # court-circuite le serveur MCP
```

Si le serveur MCP répond mais pas Live : la Control Surface n'est presque toujours
pas active. Si un tool MCP échoue là où `ableton_raw.py` passe, le bug est dans
`MCP_Server/server.py`, pas dans le Remote Script.

## Méthode de montage audio

L'ordre découle des limites du LOM et ne se négocie pas :

1. **Convertir la source en WAV** — `python3 preparer_extrait.py source.mp3 /mnt/e/…/source.wav`
2. **Repérer le passage** sur le WAV
3. **Découper l'extrait, fondus compris** —
   `python3 preparer_extrait.py source.wav extrait.wav --debut 45.5 --duree 12 --fondu-sortie 1.0 --tempo 117`
4. **Poser à la position finale, sans warping** —
   `create_arrangement_audio_clip(track_index=N, file_path=r"E:\...", start_bar=..., warp=False)`
5. **Relire** ce que Live annonce — l'étirement doit être à 0,00 %
6. **Exporter à la main** (Ctrl + Maj + R)

## Leçons mesurées

- **Un contrôle doit REFUSER, pas avertir.** `preparer_extrait.py` affichait
  « ATTENTION » au-delà de 5 ms et rendait 0 ; il refuse désormais au-delà de
  2 échantillons. Éprouvé par mutation.
- **Compter en échantillons, pas en secondes, n'est pas nécessaire ici** : `-ss` +
  `-t` en secondes sort à zéro échantillon d'écart sur quatre durées non rondes
  (7,1234 · 3,00001 · 12,5 · 0,9999 s). À 48 kHz la granularité est de 20,8 µs,
  là où une image vidéo en vaut 33 ms.
- **Le tempo par autocorrélation sans interpolation ment de ±3 %** : à 43 trames/s,
  120 BPM tombe entre deux décalages entiers et se lit 117,4 ou 123,0. Corrigé par
  interpolation parabolique (±0,6 BPM mesuré de 80 à 175 BPM), fixé par un test.
