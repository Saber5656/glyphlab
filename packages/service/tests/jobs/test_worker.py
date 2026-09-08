import multiprocessing
import os
import time

from worker_fixtures import hangs

from glyphlab_service.jobs.ipc import ChildError
from glyphlab_service.jobs.worker import execute_child


def crashes(req, progress):
    os._exit(1)


def large_result(req, progress):
    return b"x" * 2**20


def test_timeout_kills_child():
    before = {p.pid for p in multiprocessing.active_children()}
    start = time.monotonic()
    result = execute_child(None, 2, runner=hangs)
    assert isinstance(result, ChildError) and result.code == "E_TRACE_TIMEOUT"
    assert time.monotonic() - start < 10
    assert {p.pid for p in multiprocessing.active_children()} == before


def test_crash_is_internal():
    result = execute_child(None, 5, runner=crashes)
    assert result.code == "E_INTERNAL"


def test_large_result_does_not_deadlock_pipe():
    assert execute_child(None, 5, runner=large_result) == b"x" * 2**20
