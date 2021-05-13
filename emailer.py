import base64
import os

import jinja2
import sendgrid
from sendgrid.helpers.mail import Attachment
from sendgrid.helpers.mail import Content
from sendgrid.helpers.mail import ContentId
from sendgrid.helpers.mail import Disposition
from sendgrid.helpers.mail import Email
from sendgrid.helpers.mail import FileContent
from sendgrid.helpers.mail import FileName
from sendgrid.helpers.mail import FileType
from sendgrid.helpers.mail import Mail
from sendgrid.helpers.mail import Personalization
from sendgrid.helpers.mail import To

from app import logger


def create_email(address, subject, template_name, context, attachment_filenames):
    templateLoader = jinja2.FileSystemLoader(searchpath="templates")
    templateEnv = jinja2.Environment(loader=templateLoader)
    html_template = templateEnv.get_template(template_name + ".html")

    html_to_send = html_template.render(context)
    content = Content("text/html", html_to_send)

    support_email = Email("support@unpaywall.org", "Unpaywall Team")
    to_email = To(address)

    email = Mail(support_email, to_email, subject, content)
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
    if attachment_type == "csv":
        my_attachment.file_type = FileType("application/{}".format(attachment_type))
    else:
        my_attachment.file_type = FileType("application/text")
    my_attachment.file_name = FileName("results.{}".format(attachment_type))
    my_attachment.disposition = Disposition("attachment")
    my_attachment.content_id = ContentId("results file")
    with open(filename, 'rb') as f:
        data = f.read()
    my_attachment.file_content = FileContent(base64.b64encode(data).decode())
    email.add_attachment(my_attachment)
    return email


def send(email, for_real=False):
    if for_real:
        sg = sendgrid.SendGridAPIClient(api_key=os.environ.get('SENDGRID_API_KEY'))
        email_get = email.get()
        sg.client.mail.send.post(request_body=email_get)
        print("Sent an email")
    else:
        print("Didn't really send")



