import os

from slack import WebClient

slack_token = os.environ['SLACK_BOT_TOKEN']
sc = WebClient(slack_token)


def post_alert(message):
    sc.chat_postMessage(
        channel="#alerts",
        text=message
    )