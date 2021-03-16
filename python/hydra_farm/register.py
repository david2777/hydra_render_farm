"""Registers This Node"""
import sys

from MySQLdb import IntegrityError

from hydra_farm.utils import hydra_utils
from hydra_farm.utils.logging_setup import logger
from hydra_farm.database.hydra_db import HydraRenderNode, Transaction


def main():
    """Register this node in the database.

    Returns:
        None

    """
    logger.info('register running from %s', sys.argv[0])
    node = HydraRenderNode({})
    node.host = hydra_utils.my_host_name()
    node.platform = sys.platform
    try:
        with Transaction() as t:
            node.insert(t)
            logger.info("Node inserted into database!")
    except IntegrityError:
        logger.info("Host %s already exists in the HydraRenderNode table on the database", node.host)


if __name__ == "__main__":
    main()
