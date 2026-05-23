from io import BytesIO
from rq import get_current_job
from rq.job import Job
from replay_parser import ReplayParser
from renderer.render import RenderDual
from tempfile import NamedTemporaryFile
from utils.exceptions import ReplayParsingError, ReplayRenderingError
from utils.connection import REDIS
from utils.logging import LOGGER


def render_dual(
    user_id: int,
    replay_bytes_1: bytes,
    replay_bytes_2: bytes,
    fps: int,
    quality: int,
    anon: bool,
    green_tag: str | None,
    red_tag: str | None,
):
    job: Job = get_current_job()  # type: ignore
    job.meta["status"] = "Reading"
    job.save_meta()

    try:
        try:
            with BytesIO(replay_bytes_1) as bio1, BytesIO(replay_bytes_2) as bio2:
                replay_data_1 = ReplayParser(
                    bio1, strict=True
                ).get_info()["hidden"]["replay_data"]
                replay_data_2 = ReplayParser(
                    bio2, strict=True
                ).get_info()["hidden"]["replay_data"]
        except Exception as e:
            LOGGER.exception("Replay parsing failed")
            raise ReplayParsingError from e
        else:
            job.meta["status"] = "Rendering"
            job.save_meta()

            def progress_cb(per: float):
                job.meta["progress"] = per
                job.save_meta()

            try:
                renderer = RenderDual(
                    green_replay_data=replay_data_1,
                    red_replay_data=replay_data_2,
                    green_tag=green_tag,
                    red_tag=red_tag,
                )
                with NamedTemporaryFile(suffix=".mp4") as tmp:
                    renderer.start(tmp.name, fps, quality, progress_cb=progress_cb)
                    tmp.seek(0)
                    return tmp.read()
            except Exception as e:
                LOGGER.exception("Dual replay rendering failed")
                raise ReplayRenderingError from e
    except Exception as e:
        return e
    finally:
        REDIS.set(f"cooldown_{user_id}", "", ex=60)
