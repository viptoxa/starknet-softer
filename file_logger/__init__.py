import logging
from pathlib import Path

file_handler = logging.FileHandler(Path(__file__).parents[1] / 'starknet.log')
file_formatter = logging.Formatter(
    '%(asctime)s %(levelname)-8s %(message)s', datefmt='%Y-%m-%d %H:%M:%S'
)
file_handler.setFormatter(file_formatter)
file_logger = logging.getLogger('FileLogger')
file_logger.addHandler(file_handler)
file_logger.setLevel(logging.INFO)
file_logger.propagate = False
