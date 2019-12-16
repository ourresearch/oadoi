import json

from app import logger


def handle_papertrail_alert(alert):
    logger.info(u'got this papertrail alert:\n{}'.format(json.dumps(alert)))
    return alert