import os
import pathlib
import logging
from logging.config import dictConfig
from dotenv import load_dotenv

load_dotenv()

DISCORD_API_SECRET = os.getenv("DISCORD_API_TOKEN")
FIREBASE_API_SECRET = os.getenv("FIREBASE_URL")
DISCORD_WEBHOOK_URL_SECRET = os.getenv("WEBHOOK_URL")
HEADERS = {"Content-Type" : "application/json"}
BASE_DIR = pathlib.Path(__file__).parent
COGS_DIR = BASE_DIR / "cogs"

LOGGING_CONFIG = {
    "version" : 1,
    "disabled_existing_loggers" : False,
    "formatters" : {
        "verbose" : {
            "format" : "%(levelname)-10s - %(asctime)s - %(module)-15s : %(message)s"
        },
        "standard" : {
            "format" : "%(levelname)-10s - %(name)-15s : %(message)s"
        }
    },
    "handlers" : {
        "console" : {
            'level' : "DEBUG",
            'class' : "logging.StreamHandler",
            'formatter' : "standard"
        },
        "console2" : {
            'level' : "WARNING",
            'class' : "logging.StreamHandler",
            'formatter' : "standard"
        },
        "file" : {
            'level' : "INFO",
            'class' : "logging.FileHandler",
            'filename' : "logs/infos.log",
            'mode' : "w",
            'formatter' : "verbose"
        },
    },
    "loggers" : {
        "bot" : {
            'handlers' : ['console'],
            "level" : "INFO",
            "propagate" : False
        },
        "discord" : {
            'handlers' : ['console2', "file"],
            "level" : "INFO",
            "propagate" : False
        },
        "cogs" : {
            'handlers' : ['console', "file"],
            "level" : "INFO",
            "propagate" : False
        },
        "tree" : {
            'handlers' : ['console', "file"],
            "level" : "INFO",
            "propagate" : False
        }
    }
}

dictConfig(LOGGING_CONFIG)