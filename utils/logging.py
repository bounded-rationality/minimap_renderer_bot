import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
LOGGER = logging.getLogger("mmr")
LOGGER_BOT = logging.getLogger("mmr-bot")
