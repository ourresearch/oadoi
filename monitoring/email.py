import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail


def send_email(message):
    message = Mail(
        from_email='support@unpaywall.org',
        to_emails='dev@ourresearch.org',
        subject='Unpaywall Data Feed Warning',
        html_content=message + '<br><br>'
    )
    sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
    response = sg.send(message)
    return response.status_code
