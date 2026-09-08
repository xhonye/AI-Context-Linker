from src.app import run


def test_run() -> None:
    assert run() == 1
