import pytest

from preparer_extrait import construire_filtre, parse_temps, refuser_chemin_wsl


@pytest.mark.parametrize("text, seconds", [
    ("93.4", 93.4),
    ("1:33.4", 93.4),
    ("0:01:33.4", 93.4),
    ("1:00:00", 3600.0),
])
def test_parse_temps_accepts_seconds_and_clock_notation(text, seconds):
    assert parse_temps(text) == pytest.approx(seconds)


def test_parse_temps_refuses_garbage():
    with pytest.raises(SystemExit):
        parse_temps("1m33")


def test_no_fade_means_no_filter():
    assert construire_filtre(10.0, 0.0, 0.0) == ""


def test_fade_out_ends_exactly_at_the_end_of_the_extract():
    filtre = construire_filtre(12.0, 0.5, 1.5)
    assert filtre == ("afade=t=in:st=0:d=0.500000,"
                      "afade=t=out:st=10.500000:d=1.500000")


def test_destination_under_wsl_is_refused():
    with pytest.raises(SystemExit):
        refuser_chemin_wsl("/home/user/x.wav", "La destination")


def test_destination_on_a_windows_drive_is_translated():
    assert refuser_chemin_wsl("/mnt/e/x.wav", "La destination") == "E:\\x.wav"
