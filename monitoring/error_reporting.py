import json

from app import logger
from monitoring.slack import post_alert


def handle_papertrail_alert(alert):
    payload = json.loads(alert.values['payload'])

    pp_alert = json.dumps(payload, indent=2)
    logger.info(u'got this papertrail alert:\n{}'.format(pp_alert))
    post_alert(pp_alert)
    return alert
