from utils.connection import REDIS
from utils.logging import LOGGER
from rq.worker import Worker
from rq import Queue, Connection


def run_worker(queues: list[str] | None = None):
    queues = queues if queues else ["single"]
    LOGGER.info(f"Starting worker for queues: {queues}")

    with Connection(REDIS):
        worker = Worker(map(Queue, queues))
        worker.work()
