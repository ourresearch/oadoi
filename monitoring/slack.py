import os

from slackclient import SlackClient

slack_token = os.environ['SLACK_BOT_TOKEN']
sc = SlackClient(slack_token)


def post_alert(message):
    sc.api_call(
        "chat.postMessage",
        channel="#alerts",
        text=message
    )