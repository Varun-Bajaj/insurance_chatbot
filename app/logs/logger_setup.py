import logging
from logs import constants
from utilities import logging_utils


def setup_logger(logger_name, log_file=None, level='DEBUG'):
    config = logging_utils.create_and_load_config_file()
    logging.config.dictConfig(config)
    my_logger = logging_utils.create_logger(logger_name,
                                            [constants.CONST_SOCKET_HANDLER, constants.CONST_ROTATING_FILE_HANDLER],
                                            logging_level=level,
                                            host='localhost', port=9020)
    return my_logger
