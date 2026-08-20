#!/usr/bin/env python3
"""Decouper un extrait audio, fondus compris, pret a poser dans Live.

Pourquoi cet outil existe
-------------------------
Live 12.4.3 ne sait pas faire ces deux choses depuis un script, c'est mesure et
non suppose (voir la skill `piloter-ableton-live`) :

- **Rogner un clip d'arrangement.** `start_time` / `end_time` sont en lecture
  seule, `start_marker` est remis a zero en silence, `end_marker` est accepte,
  relu tel quel, et ne change rien.
- **Faire un fondu.** Les clips d'arrangement refusent toute enveloppe
  d'automation, et le LOM n'expose aucune ecriture d'automation d'arrangement.

Donc l'extrait doit arriver dans Live **deja a la bonne longueur et deja
fondu**. C'est ce que fait ce script, a l'echantillon pres.

Troisieme piege, traite ici aussi : Live **warpe** tout import par defaut, ce
qui etire l'audio sur la grille (mesure : 15,085 s -> 16,000 s, +6,1 %). Le
script rappelle donc de poser le clip avec `warp=False`, et donne la longueur
en beats pour savoir ou le placer.

Usage
-----
    python3 preparer_extrait.py SOURCE DESTINATION --debut 45.5 --duree 12.0
    python3 preparer_extrait.py SOURCE DESTINATION --debut 1:23.4 --fin 1:35.4 \\
        --fondu-entree 0.5 --fondu-sortie 1.2 --tempo 118

Les temps s'ecrivent en secondes (`93.4`) ou en `m:s` (`1:33.4`).

ffmpeg n'existe que cote Windows sur cette machine : les chemins `/mnt/X/...`
sont traduits en `X:\\...`. La destination **doit** etre sur un disque Windows,
jamais sous `/home` : Live ne sait pas lire un chemin WSL.
"""
import argparse
import os
import subprocess
import sys

FFMPEG = "ffmpeg.exe"
FFPROBE = "ffprobe.exe"


def to_windows_path(path):
    """Traduire /mnt/e/x en E:\\x — ffmpeg et Live sont des binaires Windows."""
    real = os.path.abspath(path)
    if real.startswith("/mnt/") and len(real) > 6 and real[6] == "/":
        return real[5].upper() + ":" + real[6:].replace("/", "\\")
    return real


def refuser_chemin_wsl(path, role):
    """Un media lu par Live doit vivre sur un disque Windows.

    Un process Windows qui lit \\\\wsl.localhost\\... plante ou rend faux. Mieux
    vaut refuser maintenant que produire un fichier que Live ignorera.
    """
    windows = to_windows_path(path)
    if len(windows) < 2 or windows[1] != ":":
        raise SystemExit(
            "{0} est sous WSL ({1}) : Live ne pourra pas le lire.\n"
            "Ecrire sur un disque Windows, par exemple "
            "/mnt/e/WORK/VIDEO/teaser88_v2/audio/".format(role, path))
    return windows


def parse_temps(texte):
    """Accepter 93.4, 1:33.4 ou 0:01:33.4."""
    parts = str(texte).strip().split(":")
    try:
        secondes = 0.0
        for part in parts:
            secondes = secondes * 60.0 + float(part)
        return secondes
    except ValueError:
        raise SystemExit("Temps illisible : {0!r} (attendu 93.4 ou 1:33.4)".format(texte))


def duree_reelle(path):
    """Duree **decodee**, pas celle annoncee par le conteneur.

    Sur un mp3 les deux different : le conteneur annoncait 15,000 s la ou le
    decodage rend 15,085 s. C'est la seconde qui compte, c'est elle que Live
    joue, et c'est sur elle qu'un calage de levres se fait ou se rate.
    """
    windows = to_windows_path(path)
    out = subprocess.run(
        [FFPROBE, "-v", "error", "-select_streams", "a:0",
         "-show_entries", "stream=sample_rate,channels,duration",
         "-of", "default=nw=1", windows],
        capture_output=True, text=True)

    infos = {}
    for ligne in out.stdout.splitlines():
        cle, _, valeur = ligne.partition("=")
        valeur = valeur.strip()
        if cle and valeur and valeur != "N/A":
            infos.setdefault(cle, valeur)

    # Compter les echantillons en decodant vraiment. `-count_samples` aurait
    # suffi mais ffprobe 8 l'a retire ; un decodage vers du PCM brut donne le
    # meme chiffre et ne depend d'aucune option qui puisse disparaitre.
    try:
        rate = int(infos["sample_rate"])
    except (KeyError, ValueError):
        return infos

    decode = subprocess.run(
        [FFMPEG, "-v", "error", "-i", windows, "-f", "s16le", "-ac", "1", "-"],
        capture_output=True)
    if decode.returncode == 0 and decode.stdout:
        infos["duree_decodee"] = (len(decode.stdout) // 2) / float(rate)
    else:
        try:
            infos["duree_decodee"] = float(infos.get("duration", ""))
        except ValueError:
            pass
    return infos


def construire_filtre(duree, fondu_entree, fondu_sortie):
    """Chaine afade. Les fondus sont cuits dans le fichier, faute de mieux."""
    filtres = []
    if fondu_entree > 0:
        filtres.append("afade=t=in:st=0:d={0:.6f}".format(fondu_entree))
    if fondu_sortie > 0:
        debut = max(0.0, duree - fondu_sortie)
        filtres.append("afade=t=out:st={0:.6f}:d={1:.6f}".format(debut, fondu_sortie))
    return ",".join(filtres)


def main():
    p = argparse.ArgumentParser(
        description="Decouper un extrait audio pret a poser dans Live.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__)
    p.add_argument("source")
    p.add_argument("destination", help="WAV a ecrire, sur un disque Windows")
    p.add_argument("--debut", default="0", help="debut dans la source (s ou m:s)")
    p.add_argument("--duree", default=None, help="duree de l'extrait (s ou m:s)")
    p.add_argument("--fin", default=None, help="fin dans la source (alternative a --duree)")
    p.add_argument("--fondu-entree", type=float, default=0.0, help="secondes")
    p.add_argument("--fondu-sortie", type=float, default=0.0, help="secondes")
    p.add_argument("--tempo", type=float, default=120.0,
                   help="BPM du set Live, pour convertir la duree en beats")
    p.add_argument("--sr", type=int, default=0,
                   help="frequence de sortie (0 = garder celle de la source)")
    p.add_argument("--bits", type=int, choices=(16, 24), default=24)
    p.add_argument("--ecraser", action="store_true")
    args = p.parse_args()

    if not os.path.exists(args.source):
        raise SystemExit("Source introuvable : " + args.source)
    if os.path.exists(args.destination) and not args.ecraser:
        raise SystemExit(
            "La destination existe deja : {0}\n"
            "Ajouter --ecraser pour la remplacer.".format(args.destination))

    src_win = to_windows_path(args.source)
    dst_win = refuser_chemin_wsl(args.destination, "La destination")

    infos_src = duree_reelle(args.source)
    duree_src = infos_src.get("duree_decodee")

    debut = parse_temps(args.debut)
    if args.duree is not None:
        duree = parse_temps(args.duree)
    elif args.fin is not None:
        duree = parse_temps(args.fin) - debut
    elif duree_src:
        # Sans bornes, convertir tout le fichier. C'est le geste d'entree du
        # projet : passer un mp3 du commerce en WAV avant de le toucher.
        duree = duree_src - debut
    else:
        raise SystemExit("Donner --duree ou --fin (duree source illisible).")
    if duree <= 0:
        raise SystemExit("Duree nulle ou negative : {0:.3f} s".format(duree))
    if duree_src and debut + duree > duree_src + 0.001:
        raise SystemExit(
            "L'extrait deborde la source : {0:.3f}s + {1:.3f}s > {2:.3f}s".format(
                debut, duree, duree_src))

    if args.fondu_entree + args.fondu_sortie > duree:
        raise SystemExit(
            "Les fondus ({0:.3f}s + {1:.3f}s) depassent l'extrait ({2:.3f}s).".format(
                args.fondu_entree, args.fondu_sortie, duree))

    os.makedirs(os.path.dirname(os.path.abspath(args.destination)), exist_ok=True)

    # -ss APRES -i : ffmpeg decode depuis le debut et coupe a l'echantillon.
    # Le seek rapide (-ss avant -i) se cale sur une frame mp3, ce qui suffit
    # pour ecouter mais pas pour caler des levres.
    cmd = [FFMPEG, "-v", "error", "-y" if args.ecraser else "-n", "-i", src_win,
           "-ss", "{0:.6f}".format(debut), "-t", "{0:.6f}".format(duree)]
    filtre = construire_filtre(duree, args.fondu_entree, args.fondu_sortie)
    if filtre:
        cmd += ["-af", filtre]
    if args.sr:
        cmd += ["-ar", str(args.sr)]
    cmd += ["-c:a", "pcm_s24le" if args.bits == 24 else "pcm_s16le",
            "-map_metadata", "-1", dst_win]

    done = subprocess.run(cmd, capture_output=True, text=True)
    if done.returncode != 0:
        sys.stderr.write(done.stderr)
        raise SystemExit("ffmpeg a echoue (code {0}).".format(done.returncode))

    infos_dst = duree_reelle(args.destination)
    obtenue = infos_dst.get("duree_decodee", 0.0)
    beats = obtenue * args.tempo / 60.0
    ecart_ms = (obtenue - duree) * 1000.0

    print("Extrait ecrit : {0}".format(dst_win))
    print("  source     {0:.4f} s @ {1} Hz".format(
        duree_src or 0.0, infos_src.get("sample_rate", "?")))
    print("  demande    {0:.4f} s  (de {1:.4f} a {2:.4f})".format(duree, debut, debut + duree))
    print("  obtenu     {0:.4f} s  ({1:+.2f} ms)".format(obtenue, ecart_ms))
    if args.fondu_entree or args.fondu_sortie:
        print("  fondus     {0:.3f} s en entree, {1:.3f} s en sortie (cuits dans le fichier)".format(
            args.fondu_entree, args.fondu_sortie))
    print("  a {0:g} BPM  {1:.4f} beats  =  {2:.4f} mesures en 4/4".format(
        args.tempo, beats, beats / 4.0))
    if abs(ecart_ms) > 5.0:
        print("  ATTENTION : ecart de {0:+.1f} ms avec la duree demandee.".format(ecart_ms))
    print()
    print("  Poser dans Live SANS warping, sinon Live etire l'extrait sur la grille :")
    print("    create_arrangement_audio_clip(track_index=N, warp=False,")
    print("        file_path=r\"{0}\", start_bar=..., start_beat=...)".format(dst_win))
    return 0


if __name__ == "__main__":
    sys.exit(main())
