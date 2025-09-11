import logging
import sys

def setup_logger(name: str = "x5-ai-checker", level: int = logging.INFO) -> logging.Logger:
    """
    Создаёт и настраивает логгер.
    Вывод в stdout (важно для Docker), формат: [уровень] время — сообщение.
    """
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            "[%(levelname)s] %(asctime)s — %(name)s — %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    logger.setLevel(level)
    return logger


# Глобальный логгер для проекта
logger = setup_logger()
