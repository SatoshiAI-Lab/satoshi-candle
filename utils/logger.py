import logging
import sys


APP_TITLE = 'OHLCV-WS-Pusher-Server'

logger = logging.getLogger(APP_TITLE)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(logging.Formatter('[%(asctime)s][%(levelname)s][%(pathname)s:%(lineno)s]%(message)s'))
logger.addHandler(console_handler)
logger.setLevel(logging.INFO)
