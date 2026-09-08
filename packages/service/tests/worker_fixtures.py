"""Importable spawn-process fixtures shared by worker and abuse tests."""

import time


def hangs(req, progress):
    progress("trace")
    while True:
        time.sleep(1)
