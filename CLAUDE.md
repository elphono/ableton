# Piloter Ableton Live 12 depuis Claude Code

Serveur MCP `ableton` : fork maison de
[uisato/ableton-mcp-extended](https://github.com/uisato/ableton-mcp-extended).

## Où vivent les choses

| Quoi | Où |
|---|---|
| Code du serveur MCP (fork) | `C:\Users\elphono\dev\ableton-mcp` (`/mnt/c/Users/elphono/dev/ableton-mcp`) |
| Remote Script chargé par Live | `C:\Users\elphono\Documents\Ableton\User Library\Remote Scripts\AbletonMCP\__init__.py` |
| Ableton Live 12.4.3 Suite | `E:\Programs\Ableton` |
| Venv Windows du serveur | `C:\Users\elphono\dev\ableton-mcp\.venv` (Python 3.11.9) |
| Venv WSL pour l'analyse audio | `/home/elphono/workspace/misc/ableton/.venv` (numpy, scipy) |
| ffmpeg / ffprobe | Windows uniquement, déjà dans le PATH (`ffmpeg.exe` 8.1.2) |

**Le Remote Script est une copie**, pas un lien. Après toute modification dans
le repo, le redéployer :

```bash
cp /mnt/c/Users/elphono/dev/ableton-mcp/AbletonMCP_Remote_Script/__init__.py \
   "/mnt/c/Users/elphono/Documents/Ableton/User Library/Remote Scripts/AbletonMCP/__init__.py"
```

…puis **redémarrer Live**.

**Vérifié le 2026-08-16 : basculer la Control Surface sur *None* puis de nouveau
sur *AbletonMCP* ne recharge PAS un script modifié.** Live garde le module dans
`sys.modules` ; le on/off recrée l'instance à partir du code déjà en mémoire, et
l'ancienne version continue de répondre. Seul un redémarrage complet de Live
recharge le fichier. Idem pour un script nouvellement posé, qui n'apparaît dans
la liste qu'après redémarrage.

Le symptôme est trompeur : le serveur répond normalement, mais avec l'ancien
comportement. En cas de doute, appeler un handler qui n'existe que dans la
nouvelle version.

### Où se trouve le réglage (Live 12)

En Live 12 le menu s'appelle **Réglages** (*Settings*), plus « Préférences »
comme en Live 11 :

**Options → Réglages…** (ou **Ctrl + ,**) → onglet **« Tempo & MIDI »**
→ section **Control Surface** → *AbletonMCP*.

Attention : le manuel officiel de Live 12 parle d'un onglet
« Link, Tempo & MIDI », mais **Live 12.4 l'a scindé** en deux onglets distincts,
*Link* et *Tempo & MIDI*. C'est le second qu'il faut. Vérifié sur 12.4.3.

Laisser **Entrée** et **Sortie** sur *Aucune* : le script ne passe pas par le
MIDI, il ouvre un socket TCP. Live accepte 6 surfaces de contrôle simultanées.

## Architecture

```
Claude Code (WSL2) --stdio--> cmd.exe /c run_server.bat (Windows)
                                  └─ serveur MCP Python --TCP 9877--> Remote Script dans Live
```

Tout ce qui est Windows reste Windows. Le TCP est du pur `localhost` Windows :
pas de bind `0.0.0.0`, pas de règle de pare-feu, pas d'IP d'hôte WSL.

## Pièges vérifiés

| Piège | Ce qu'il faut faire |
|---|---|
| Les variables d'environnement **ne franchissent pas** l'interop WSL→Windows | Elles sont posées dans `run_server.bat`, pas côté WSL |
| Console Windows en cp1252 : tout nom de piste accentué lève `UnicodeEncodeError` | `run_server.bat` force `-X utf8` + `PYTHONUTF8=1` |
| Un process Windows qui lit un chemin `\\wsl.localhost\...` plante ou rend faux | **Tous les médias sur `E:` ou `C:`**, jamais sous `/home` |
| `cmd.exe` lancé depuis un cwd WSL affiche un avertissement UNC | Il part sur **stderr**, stdout reste propre — sans danger pour le JSON-RPC |
| MCP SDK 2.x a retiré `mcp.server.fastmcp` | Épinglé à `mcp[cli]<2` dans `pyproject.toml` |
| `pyproject.toml` amont déclare `AbletonMCP_UDP`, qui n'existe pas | Retiré du fork |
| Live n'expose **aucune API d'export audio** dans le LOM | L'export final se fait à la main (Ctrl+Maj+R) ou par automatisation clavier |

## Extensions maison ajoutées au fork

Le fork amont ne savait pas faire ceci ; c'est ajouté des deux côtés
(Remote Script + serveur MCP) :

- `create_audio_track`, `create_return_track` — il n'existait que des pistes MIDI
- `set_track_state` — mute / solo / arm
- `get_sends` / `set_send` — effets en bus
- `get_mixer_info` — instantané complet du mixer en un appel
- `inspect_lom` — **introspection du Live Object Model à l'exécution**
- `get_clip_notes` — **relire** les notes d'un clip. L'amont ne savait
  qu'écrire, ce qui n'est qu'une demi-boucle : sans relecture on ne peut ni
  vérifier ni corriger.
- `remove_clip_notes` — supprimer des notes dans une fenêtre temps × hauteur.
  `add_notes_to_clip` n'ajoute que : sans cela une erreur est définitive.
- `delete_session_clip` — vider un slot de session
- `measure_arrangement_clip` — mesurer l'étirement d'un clip **déjà posé**.
  Existe pour le *moment* où il mesure, pas pour ce qu'il mesure : une lecture
  faite dans le tick qui a écrit `warping` renvoie l'étendue d'avant (voir
  ci-dessous)

Corrigés parce qu'ils mentaient :

- `create_arrangement_audio_clip` prend `warp` et **renvoie l'étirement
  constaté**, au lieu de laisser Live étirer de 6 % en silence. **Corrigé le
  2026-08-16** : il mesurait dans le tick où il venait d'écrire `warping`, donc
  sur l'étendue d'avant — un WAV de 6,000 s posé avec `warp=False` était annoncé
  « 8,000 s, +33,33 % ». Le clip était juste, la mesure était fausse. La mesure
  se fait maintenant dans un **second aller-retour**
  (`measure_arrangement_clip`), seul moyen de tomber après le recalcul de Live
- `set_arrangement_clip_property` renvoie les **conséquences observables**
  (étendue, boucle, warping) et signale les propriétés inertes
- `set_clip_fade` cherchait « Volume » quand Live dit « Track Volume », et
  rampait vers `param.max` = **+6 dB** au lieu du niveau nominal
- `manage_clip_automation` visait un clip d'arrangement : il ne pouvait
  **jamais** aboutir
- `load_instrument_or_effect` annonçait « Devices on track: » suivi de rien
  après un chargement pourtant réussi

**Convention d'index de piste** pour les outils maison : `1..n` = pistes,
`n+1..n+r` = retours, **`0` = master**. (Les outils amont sont 1-based sans master.)

## Outils locaux

| Outil | Rôle |
|---|---|
| `check_ableton.sh` | diagnostic des 4 étages de la chaîne |
| `ableton_raw.py` | parler **directement** au Remote Script — isole une panne du serveur MCP, et atteint ce que les signatures des tools n'exposent pas |
| `preparer_extrait.py` | découper un extrait, fondus cuits dedans, en WAV prêt à poser |
| `analyse_audio.py` | tempo et tonalité d'un extrait |

### Ce que le LOM de Live 12.4.3 expose vraiment (mesuré, pas supposé)

**Corrigé le 2026-08-16 après exécution.** La version précédente de ce tableau
était fausse : elle listait des propriétés *présentes* et en concluait qu'elles
étaient *utiles*. Elles sont présentes, acceptées, relues telles quelles — et
sans effet. Le détail complet est dans la skill `piloter-ableton-live` ; ici
l'essentiel.

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
| Toute méthode d'export / render / bounce | **AUCUNE** — l'export final est manuel |
| `Track.create_audio_clip(path, position)` | présent → seule voie pour poser un fichier |

**Conséquence** : ni découpe, ni déplacement, ni fondu ne sont scriptables dans
l'arrangement. **Live assemble, il ne monte pas.** Les extraits doivent arriver
déjà coupés et déjà fondus. C'est le rôle de `preparer_extrait.py`, qui rend
aussi la longueur en beats pour savoir où poser.

Un crossfade se construit toujours en superposant deux extraits sur **deux
pistes**, mais chacun porte son fondu dans son propre fichier.

`manage_clip_automation` était pire qu'inutile : il résolvait un clip
d'arrangement, donc il ne pouvait **jamais** aboutir. Il vise maintenant les
slots de session, où les enveloppes sont légales.

### Les deux distorsions temporelles qui cassent le lip-sync

Mesurées, cumulatives, et parfaitement silencieuses :

1. **Live warpe tout import** : un fichier de 15,000 s devient 16,000 s
   (**+6,1 %**). Poser avec `warp=False`.
2. **Un mp3 ne commence pas au même endroit dans Live et dans ffmpeg** :
   **84,6 ms** d'écart, soit 2,5 images à 29,97 fps — c'est le silence d'amorce
   LAME, que ffmpeg retire et que Live joue. En WAV l'écart tombe à **0
   échantillon**, vérifié. Donc **jamais de mp3 dans Live**.

### `inspect_lom` d'abord, deviner jamais

L'API Python de Live change d'une version à l'autre et la documentation est en
retard. Avant d'affirmer qu'une propriété existe ou qu'elle est modifiable :

```
inspect_lom("tracks[0].arrangement_clips[0]")
```

## Diagnostic

```bash
./check_ableton.sh                       # les 4 étages, testés séparément
python3 ableton_raw.py get_session_info  # court-circuite le serveur MCP
```

Si le serveur MCP répond mais que Live ne répond pas, c'est presque toujours
que la Control Surface n'est pas active dans les préférences de Live.

Si un tool MCP échoue là où `ableton_raw.py` passe, le bug est dans
`MCP_Server/server.py`, pas dans le Remote Script.

## Méthode de montage audio

Live n'offre ni découpe, ni déplacement, ni fondu (voir plus haut). L'ordre des
opérations en découle et ne se négocie pas :

1. **Convertir la source en WAV** — supprime les 84,6 ms de décalage du mp3
   `python3 preparer_extrait.py source.mp3 /mnt/e/.../source.wav`
2. **Repérer le passage** sur le WAV (skill `mesurer-son-et-image`)
3. **Découper l'extrait, fondus compris**
   `python3 preparer_extrait.py source.wav extrait.wav --debut 45.5 --duree 12 --fondu-sortie 1.0 --tempo 117`
4. **Poser à la position finale, sans warping**
   `create_arrangement_audio_clip(track_index=N, file_path=r"E:\...", start_bar=..., warp=False)`
5. **Relire** ce que Live annonce — l'étirement doit être à 0,00 %
6. **Exporter à la main** (Ctrl + Maj + R) : aucune API ne le fait
