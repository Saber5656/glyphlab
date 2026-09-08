"""A dispatcher owns child lifetimes; all persistent effects remain in the parent."""

import logging
import multiprocessing
import os
import signal
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from ..db.models import Job, utcnow
from .ipc import ChildError
from .queue import claim_next, requeue_expired


def child_entry(connection, req, runner):
    if os.name == "posix":
        os.setsid()
    try:

        def progress(stage):
            connection.send({"stage": stage})

        result = runner(req, progress)
        connection.send(result)
    except BaseException as exc:
        from glyphlab.errors import GlyphlabError

        if isinstance(exc, GlyphlabError):
            connection.send(ChildError(exc.code, exc.detail))
        else:
            connection.send(ChildError("E_INTERNAL"))
    finally:
        connection.close()


def terminate_child(process):
    if process.is_alive():
        if os.name == "posix":
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                process.terminate()
        else:
            process.terminate()
        process.join(5)
    if process.is_alive():
        if os.name == "posix":
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                process.kill()
        else:
            process.kill()
        process.join(1)


def execute_child(req, timeout_s, *, runner=None, renew=lambda: None, stop_event=None):
    if runner is None:
        from .child import run_job_payload

        runner = run_job_payload
    ctx = multiprocessing.get_context("spawn")
    parent, child = ctx.Pipe(duplex=False)
    process = ctx.Process(target=child_entry, args=(child, req, runner), name="glyphlab-job")
    process.start()
    child.close()
    start = time.monotonic()
    next_renew = start + 30
    traced = False
    try:
        while True:
            now = time.monotonic()
            if stop_event and stop_event.is_set():
                return ChildError("E_JOB_LOST")
            if now - start >= timeout_s:
                return ChildError("E_TRACE_TIMEOUT" if traced else "E_INTERNAL")
            if now >= next_renew:
                renew()
                next_renew = now + 30
            if parent.poll(min(0.1, max(0, timeout_s - (now - start)))):
                try:
                    message = parent.recv()
                except EOFError:
                    return ChildError("E_INTERNAL")
                if isinstance(message, dict) and "stage" in message:
                    traced = traced or message["stage"] == "trace"
                    continue
                return message
            if not process.is_alive():
                return ChildError("E_INTERNAL")
    finally:
        terminate_child(process)
        process.join(1)
        parent.close()
        process.close()


class Worker:
    def __init__(self, state):
        self.state = state
        self.stop_event = threading.Event()
        self.thread = None

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.thread = threading.Thread(target=self.run, name="glyphlab-dispatcher", daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(10)

    def run(self):
        futures = set()
        last_recovery = 0
        with ThreadPoolExecutor(max_workers=self.state.settings.job_concurrency) as pool:
            while not self.stop_event.is_set():
                try:
                    if time.monotonic() - last_recovery >= 30:
                        with self.state.session_factory() as session:
                            requeue_expired(session)
                        from .handlers import cleanup_terminal_uploads

                        cleanup_terminal_uploads(self.state)
                        last_recovery = time.monotonic()
                    futures = {f for f in futures if not f.done()}
                    if len(futures) < self.state.settings.job_concurrency:
                        with self.state.session_factory() as session:
                            job = claim_next(session)
                        if job:
                            futures.add(pool.submit(self.process, job.id))
                            continue
                except Exception:
                    logging.getLogger("glyphlab_service").error(
                        "Worker dispatch failed", extra={"error_code": "E_INTERNAL"}
                    )
                self.stop_event.wait(0.5 if futures else 2)

    def process(self, job_id):
        from .handlers import apply_result, prepare_request

        with self.state.session_factory() as session:
            job = session.get(Job, job_id)
            if not job or job.status != "running":
                return
            attempt = job.attempts

        try:
            request = prepare_request(self.state, job_id)
            if request is None:
                return

            def renew():
                with self.state.session_factory.begin() as session:
                    row = session.get(Job, job_id)
                    if row and row.status == "running" and row.attempts == attempt:
                        row.lease_expires_at = utcnow() + timedelta(seconds=180)

            result = execute_child(
                request, self.state.settings.job_timeout_s, renew=renew, stop_event=self.stop_event
            )
        except Exception as exc:
            from glyphlab.errors import GlyphlabError

            result = (
                ChildError(exc.code, exc.detail)
                if isinstance(exc, GlyphlabError)
                else ChildError("E_INTERNAL")
            )
        if self.stop_event.is_set():
            return  # Leave the lease recoverable on next boot.
        try:
            apply_result(self.state, job_id, result, expected_attempt=attempt)
        except Exception:
            logging.getLogger("glyphlab_service").error(
                "Job persistence failed", extra={"job_id": job_id, "error_code": "E_INTERNAL"}
            )
            try:
                apply_result(self.state, job_id, ChildError("E_INTERNAL"), expected_attempt=attempt)
            except Exception:
                logging.getLogger("glyphlab_service").error(
                    "Job will recover after lease expiry", extra={"job_id": job_id}
                )
