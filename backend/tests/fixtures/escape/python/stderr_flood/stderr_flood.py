import os


def flood() -> None:
    os.write(2, b"y" * (2 * 1024 * 1024))
