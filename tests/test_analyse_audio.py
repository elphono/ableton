import numpy as np
import pytest

import analyse_audio
from analyse_audio import MAJOR, MINOR, chroma, key_of, stft, tempo


@pytest.mark.parametrize("shift, profile, expected", [
    (0, MAJOR, "C maj"),
    (7, MAJOR, "G maj"),
    (9, MINOR, "A min"),
    (2, MINOR, "D min"),
])
def test_key_of_finds_the_key_of_its_own_profile(shift, profile, expected):
    key, margin = key_of(np.roll(profile, shift))
    assert key == expected
    assert margin > 0


def _click_track(bpm, seconds=12.0):
    sr = analyse_audio.SR
    x = np.zeros(int(sr * seconds))
    period = int(round(sr * 60.0 / bpm))
    burst = np.random.default_rng(0).standard_normal(256)
    for start in range(0, len(x) - 256, period):
        x[start:start + 256] += burst
    return x


@pytest.mark.parametrize("bpm", [90.0, 117.0, 120.0, 128.0, 150.0, 175.0])
def test_tempo_of_a_click_track_is_among_the_candidates(bpm):
    candidates = tempo(stft(_click_track(bpm)))
    # Below the 2.5 % that whole-frame lags would allow at 120 BPM.
    assert any(abs(c - bpm) <= 1.0 for c in candidates), candidates


def test_chroma_of_a_pure_tone_peaks_on_its_pitch_class():
    sr = analyse_audio.SR
    t = np.arange(sr * 2) / sr
    a440 = np.sin(2 * np.pi * 440.0 * t)
    assert int(np.argmax(chroma(stft(a440)))) == 9  # A
