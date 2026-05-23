from utils.connection import REDIS
from utils.logging import LOGGER
from rq.worker import Worker
from rq import Queue


def run_worker(queues: list[str] | None = None):
    queues = queues if queues else ["single"]
    LOGGER.info(f"Starting worker for queues: {queues}")
    worker = Worker([Queue(q, connection=REDIS) for q in queues], connection=REDIS)
    worker.work()
