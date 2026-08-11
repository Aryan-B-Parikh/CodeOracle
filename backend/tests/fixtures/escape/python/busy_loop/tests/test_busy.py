from busy_loop import run_forever


def test_hangs_forever() -> None:
    run_forever()
