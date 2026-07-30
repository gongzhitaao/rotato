from rotato.__main__ import main


def test_unknown_rotator_returns_2(capsys):
    assert main(["definitely-not-a-rotator"]) == 2
    assert "unknown rotator" in capsys.readouterr().err


def test_no_name_returns_2(monkeypatch):
    monkeypatch.delenv("ROTATOR", raising=False)
    assert main([]) == 2
