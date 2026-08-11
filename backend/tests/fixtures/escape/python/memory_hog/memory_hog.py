def grow() -> None:
    data: list[bytes] = []
    while True:
        data.append(b"x" * (1024 * 1024))
