import json

from app import logger
from monitoring.email import send_email


def handle_papertrail_alert(alert):
    payload = json.loads(alert.values['payload'])

    pp_alert = json.dumps(payload, indent=2)
    logger.info(u'got this papertrail alert:\n{}'.format(pp_alert))
    send_email(pp_alert)
    return alert
