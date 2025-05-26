#########################################################
# Author: Yuuki (@yuuki.dn)
# Chỉ cần import vào thôi, code nó tự chạy <(")
#########################################################

from logging import Filter, StreamHandler, INFO, ERROR, Formatter, WARNING, basicConfig, FileHandler, DEBUG, getLogger
from os import makedirs
from sys import stdout, stderr
from logging.config import dictConfig

from colorama import Fore, Style, init

try:
    open(".logs/Running.log", "a").close()
except FileNotFoundError:
    makedirs(".logs", exist_ok=True)
    open(".logs/Running.log", "w").close()

asyncio_logger = getLogger("asyncio")

asyncio_logger.disabled = True


class SpectificLevelFilter(Filter):
    def __init__(self, level: int):
        super().__init__()
        self.level = level

    def filter(self, record) -> bool:
        return record.levelno == self.level

## Format (console only)
INFO_FORMAT = f"{Style.DIM}[%(asctime)s]{Style.RESET_ALL} [%(name)s:%(lineno)d] [%(funcName)s] [✅] {Fore.GREEN}[%(levelname)s] - {Fore.CYAN}%(message)s{Style.RESET_ALL}"
WARNING_FORMAT = f"{Style.DIM}[%(asctime)s]{Style.RESET_ALL} [%(name)s:%(lineno)d] [%(funcName)s] [⚠️]  {Fore.YELLOW}[%(levelname)s] - {Fore.LIGHTBLUE_EX}%(message)s{Style.RESET_ALL}"
ERROR_FORMAT = f"{Style.DIM}[%(asctime)s]{Style.RESET_ALL} [%(name)s:%(lineno)d] [%(funcName)s] [❌] {Fore.RED}[%(levelname)s] - {Fore.LIGHTRED_EX}%(message)s{Style.RESET_ALL}"
DEBUG_FORMAT = f"{Style.DIM}[%(asctime)s]{Style.RESET_ALL} [%(name)s:%(lineno)d] [%(funcName)s] [🐛] {Fore.BLUE}[%(levelname)s] - %(message)s{Style.RESET_ALL}"

DATEFMT="%d-%m-%Y %H:%M:%S"

## Create handlers
infoHandler = StreamHandler(stream=stdout)
infoHandler.setLevel(INFO)
infoHandler.addFilter(SpectificLevelFilter(INFO))
infoHandler.setFormatter(Formatter(INFO_FORMAT, datefmt=DATEFMT))

warningHandler = StreamHandler(stream=stdout)
warningHandler.setLevel(WARNING)
warningHandler.addFilter(SpectificLevelFilter(WARNING))
warningHandler.setFormatter(Formatter(WARNING_FORMAT, datefmt=DATEFMT))

errorHandler = StreamHandler(stream=stderr)
errorHandler.setLevel(ERROR)
errorHandler.addFilter(SpectificLevelFilter(ERROR))
errorHandler.setFormatter(Formatter(ERROR_FORMAT, datefmt=DATEFMT))

debugHandler = StreamHandler(stream=stderr)
debugHandler.setLevel(DEBUG)
debugHandler.addFilter(SpectificLevelFilter(DEBUG))
debugHandler.setFormatter(Formatter(DEBUG_FORMAT, datefmt=DATEFMT))

fileHandler = FileHandler(".logs/Running.log", mode="w", encoding="utf-8")
fileHandler.setLevel(INFO)
fileHandler.setFormatter(Formatter("%(asctime)s %(name)s:%(lineno)d [%(levelname)s] - %(message)s", datefmt=DATEFMT))

## Configure
basicConfig(
    level=INFO,
    handlers=[infoHandler, warningHandler, errorHandler, fileHandler, debugHandler]
)


LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "info": {
            "format": INFO_FORMAT,
            "datefmt": DATEFMT
        },
        "warning": {
            "format": WARNING_FORMAT,
            "datefmt": DATEFMT
        },
        "error": {
            "format": ERROR_FORMAT,
            "datefmt": DATEFMT
        },
        "debug": {
            "format": DEBUG_FORMAT,
            "datefmt": DATEFMT
        },
        "file": {
            "format": "%(asctime)s %(name)s:%(lineno)d [%(levelname)s] - %(message)s",
            "datefmt": DATEFMT
        }
    },
    "filters": {
        "info_filter": {
            "()": SpectificLevelFilter,
            "level": INFO
        },
        "warning_filter": {
            "()": SpectificLevelFilter,
            "level": WARNING
        },
        "error_filter": {
            "()": SpectificLevelFilter,
            "level": ERROR
        },
        "debug_filter": {
            "()": SpectificLevelFilter,
            "level": DEBUG
        }
    },
    "handlers": {
        "info_console": {
            "class": "logging.StreamHandler",
            "level": "INFO",
            "formatter": "info",
            "filters": ["info_filter"],
            "stream": "ext://sys.stdout"
        },
        "warning_console": {
            "class": "logging.StreamHandler",
            "level": "WARNING",
            "formatter": "warning",
            "filters": ["warning_filter"],
            "stream": "ext://sys.stdout"
        },
        "error_console": {
            "class": "logging.StreamHandler",
            "level": "ERROR",
            "formatter": "error",
            "filters": ["error_filter"],
            "stream": "ext://sys.stderr"
        },
        "debug_console": {
            "class": "logging.StreamHandler",
            "level": "DEBUG",
            "formatter": "debug",
            "filters": ["debug_filter"],
            "stream": "ext://sys.stderr"
        },
        "file": {
            "class": "logging.FileHandler",
            "formatter": "file",
            "level": "INFO",
            "filename": ".logs/Running.log",
            "mode": "w",
            "encoding": "utf-8"
        }
    },
    "root": {
        "level": "DEBUG",
        "handlers": ["info_console", "warning_console", "error_console", "debug_console", "file"]
    }
}

def setup_logger():
    init(autoreset=True)
    dictConfig(LOGGING_CONFIG)