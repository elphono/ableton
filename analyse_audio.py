#!/usr/bin/env python3
"""Mesurer tempo et tonalite d'un extrait audio.

Cas d'usage d'origine : un groupe joue-t-il assez pres du master du commerce
pour qu'on puisse poser le master sous une image ou l'on voit le chanteur ? Si
le tempo ou la tonalite s'ecartent, les levres ne colleront pas, quel que soit
le point de montage.

Une mesure classe, elle ne choisit pas : l'oreille tranche sur ce qui reste.

Usage :
    python analyse_audio.py fichier.mp3 [fichier2.mp3 ...]
    python analyse_audio.py --csv dossier/*.mp3

ffmpeg est appele cote Windows (ffmpeg.exe dans le PATH) : les chemins
/mnt/X/... sont traduits en X:\\... avant l'appel.
"""
import subprocess
import sys
import os
import numpy as np

from wsl_paths import to_windows_path

SR = 22050
FFMPEG = "ffmpeg.exe"

# Profils de Krumhansl-Kessler : correlation du chromagramme moyen avec le
# profil de chaque tonalite. Fiable sur de la pop tonale, pas sur du bruit.
MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
NOTES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]



def load_mono(path):
    """Decoder en float32 mono via ffmpeg, sans fichier intermediaire."""
    cmd = [
        FFMPEG, "-v", "error", "-i", to_windows_path(path),
        "-f", "f32le", "-ac", "1", "-ar", str(SR), "-",
    ]
    out = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(out, dtype="<f4").astype(np.float64)


def stft(x, n_fft=2048, hop=512):
    window = np.hanning(n_fft)
    n_frames = 1 + (len(x) - n_fft) // hop
    if n_frames < 1:
        raise ValueError("extrait trop court")
    frames = np.lib.stride_tricks.as_strided(
        x, shape=(n_frames, n_fft),
        strides=(x.strides[0] * hop, x.strides[0]),
    )
    return np.abs(np.fft.rfft(frames * window, axis=1))


def tempo(spec, hop=512, bpm_min=60.0, bpm_max=200.0):
    """Tempo par autocorrelation du flux spectral (montees d'energie seules).

    Le demi-tempo et le double-tempo sont des reponses legitimes de
    l'autocorrelation : les deux meilleurs candidats sont donc renvoyes.
    """
    flux = np.diff(spec, axis=0)
    onset = np.maximum(flux, 0).sum(axis=1)
    onset -= onset.mean()
    if onset.std() > 0:
        onset /= onset.std()

    corr = np.correlate(onset, onset, mode="full")[len(onset) - 1:]
    fps = SR / hop
    lag_min = max(1, int(fps * 60.0 / bpm_max))
    lag_max = min(len(corr) - 1, int(fps * 60.0 / bpm_min))
    if lag_max <= lag_min:
        return []

    window = corr[lag_min:lag_max]
    # Pics locaux uniquement : un maximum sur une pente n'est pas une periode.
    peaks = [
        i for i in range(1, len(window) - 1)
        if window[i] > window[i - 1] and window[i] >= window[i + 1]
    ]
    peaks.sort(key=lambda i: window[i], reverse=True)
    return [round(float(60.0 * fps / (lag_min + i + _vertex(window, i))), 1)
            for i in peaks[:2]]


def _vertex(window, i):
    """Sub-frame offset of a peak, by fitting a parabola through its neighbours.

    Lags are whole frames of 23 ms: at 120 BPM the true period, 21.5 frames,
    would otherwise round to 21 or 22 and read 123.0 or 117.4 BPM.
    """
    a, b, c = window[i - 1], window[i], window[i + 1]
    curvature = a - 2.0 * b + c
    if curvature >= 0:
        return 0.0
    return 0.5 * (a - c) / curvature


def chroma(spec, n_fft=2048):
    """Chromagramme moyen : energie repliee sur les 12 demi-tons."""
    freqs = np.fft.rfftfreq(n_fft, 1.0 / SR)
    bins = np.zeros(12)
    usable = (freqs > 55.0) & (freqs < 2000.0)
    midi = 69 + 12 * np.log2(np.maximum(freqs[usable], 1e-9) / 440.0)
    classes = np.round(midi).astype(int) % 12
    energy = spec[:, usable].mean(axis=0)
    for pitch_class in range(12):
        bins[pitch_class] = energy[classes == pitch_class].sum()
    return bins / bins.sum() if bins.sum() > 0 else bins


def key_of(chroma_vector):
    """Tonalite la plus correlee, avec l'ecart a la seconde meilleure.

    Un ecart faible veut dire que la mesure n'a pas tranche : la lire comme une
    reponse serait inventer un chiffre.
    """
    scores = []
    for shift in range(12):
        for name, profile in (("maj", MAJOR), ("min", MINOR)):
            rolled = np.roll(profile, shift)
            corr = np.corrcoef(chroma_vector, rolled)[0, 1]
            scores.append((corr, NOTES[shift] + " " + name))
    scores.sort(reverse=True)
    return scores[0][1], scores[0][0] - scores[1][0]


def analyse(path):
    x = load_mono(path)
    spec = stft(x)
    bpms = tempo(spec)
    key, margin = key_of(chroma(spec))
    return {
        "fichier": os.path.basename(path),
        "duree": len(x) / SR,
        "bpm": bpms,
        "tonalite": key,
        "marge": margin,
    }


def main():
    args = [a for a in sys.argv[1:] if a != "--csv"]
    as_csv = "--csv" in sys.argv
    if not args:
        print(__doc__)
        return 1

    if as_csv:
        print("fichier;duree_s;bpm1;bpm2;tonalite;marge")
    for path in args:
        try:
            r = analyse(path)
        except Exception as e:
            print("{0} : ECHEC — {1}".format(os.path.basename(path), e))
            continue
        bpms = r["bpm"] + [""] * 2
        if as_csv:
            print("{0};{1:.1f};{2};{3};{4};{5:.3f}".format(
                r["fichier"], r["duree"], bpms[0], bpms[1], r["tonalite"], r["marge"]))
        else:
            doubt = "  (peu sur)" if r["marge"] < 0.05 else ""
            print("{0:52s} {1:5.1f}s  BPM {2:<14s} {3}{4}".format(
                r["fichier"][:52], r["duree"],
                " ou ".join(str(b) for b in r["bpm"]) or "?",
                r["tonalite"], doubt))
    return 0


if __name__ == "__main__":
    sys.exit(main())
