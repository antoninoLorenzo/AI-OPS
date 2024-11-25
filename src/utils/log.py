import logging


def get_logger(module_name: str) -> logging.Logger:
    """
    :param module_name: __name__ should be passed
    """
    logger = logging.getLogger(module_name)

    formatter = logging.Formatter('%(levelname)s: %(name)s: %(message)s')

    logger_handler = logging.StreamHandler()
    logger_handler.setLevel(logging.DEBUG)
    logger_handler.setFormatter(formatter)

    logger.setLevel(logging.DEBUG)
    logger.addHandler(logger_handler)

    return logger