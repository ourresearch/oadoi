import base64
import os

import jinja2
import sendgrid
from sendgrid.helpers.mail.mail import Attachment
from sendgrid.helpers.mail.mail import Content
from sendgrid.helpers.mail.mail import Email
from sendgrid.helpers.mail.mail import Mail
from sendgrid.helpers.mail.mail import Personalization

from app import logger


def create_email(address, subject, template_name, context, attachment_filenames):
    templateLoader = jinja2.FileSystemLoader(searchpath="templates")
    templateEnv = jinja2.Environment(loader=templateLoader)
    html_template = templateEnv.get_template(template_name + ".html")

    html_to_send = html_template.render(context)
    content = Content("text/html", html_to_send)

    support_email = Email("support@unpaywall.org", "Unpaywall Team")
    to_email = Email(address)

    email = Mail(support_email, subject, to_email, content)
    personalization = Personalization()
    personalization.add_to(to_email)
    email.add_personalization(personalization)

    logger.info('sending email "{}" to {}'.format(subject, address))
    for filename in attachment_filenames:
        email = add_results_attachment(email, filename)

    return email


def add_results_attachment(email, filename=None):
    my_attachment = Attachment()
    attachment_type = filename.split(".")[1]
    if attachment_type=="csv":
        my_attachment.type = "application/{}".format(attachment_type)
    else:
        my_attachment.type = "application/text"
    my_attachment.filename = "results.{}".format(attachment_type)
    my_attachment.disposition = "attachment"
    my_attachment.content_id = "results file"
    with open(filename, 'rb') as f:
        data = f.read()
    my_attachment.content = base64.b64encode(data)
    email.add_attachment(my_attachment)
    return email


def send(email, for_real=False):
    if for_real:
        sg = sendgrid.SendGridAPIClient(apikey=os.environ.get('SENDGRID_API_KEY'))
        email_get = email.get()
        response = sg.client.mail.send.post(request_body=email_get)
        print("Sent an email")
    else:
        print("Didn't really send")



