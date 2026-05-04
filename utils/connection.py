import os
import redis
import redis.asyncio as aioredis
from utils.environ import check_environment_var
from utils.logging import LOGGER

check_environment_var(["REDIS_HOST", "REDIS_PORT", "REDIS_PASSWORD"])

_host = os.environ["REDIS_HOST"]
_port = int(os.environ["REDIS_PORT"])
_password = os.environ["REDIS_PASSWORD"]
_username = os.environ.get("REDIS_USERNAME", "default")

# Use TLS if REDIS_TLS=true (required for Azure Cache for Redis)
_use_tls = os.environ.get("REDIS_TLS", "false").lower() == "true"

_redis_kwargs = dict(
    host=_host,
    port=_port,
    username=_username,
    password=_password,
    ssl=_use_tls,
    ssl_cert_reqs="required" if _use_tls else None,
    decode_responses=False,
)

LOGGER.info(f"Connecting to Redis at {_host}:{_port} (TLS: {_use_tls})")

REDIS = redis.StrictRedis(**_redis_kwargs)
ASYNC_REDIS = aioredis.StrictRedis(**_redis_kwargs)
