"""Gunicorn hooks. Multi-worker Prometheus metrics need dead-worker cleanup."""
import os


def child_exit(server, worker):
    if os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
        from prometheus_client import multiprocess

        multiprocess.mark_process_dead(worker.pid)
