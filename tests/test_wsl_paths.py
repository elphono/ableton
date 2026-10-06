from wsl_paths import is_on_windows_drive, to_windows_path


def test_mounted_drive_becomes_a_windows_path():
    assert to_windows_path("/mnt/e/WORK/a b/x.wav") == "E:\\WORK\\a b\\x.wav"


def test_drive_letter_is_uppercased():
    assert to_windows_path("/mnt/c/x") == "C:\\x"


def test_wsl_path_is_left_alone():
    assert to_windows_path("/home/user/x.wav") == "/home/user/x.wav"


def test_mnt_subfolder_that_is_not_a_drive_is_left_alone():
    assert to_windows_path("/mnt/wsl/x") == "/mnt/wsl/x"


def test_only_windows_drives_are_readable_by_windows_programs():
    assert is_on_windows_drive("/mnt/e/x.wav")
    assert not is_on_windows_drive("/home/user/x.wav")
    assert not is_on_windows_drive("/mnt/wsl/x.wav")
