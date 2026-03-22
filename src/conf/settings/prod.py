from decouple import Csv

from conf.settings.base import *  # noqa: F401, F403

DEBUG = False

ALLOWED_HOSTS = config("ALLOWED_HOSTS", cast=Csv())  # noqa: F405
