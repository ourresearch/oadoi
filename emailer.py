import os
import jinja2
import base64
import sendgrid
import re
from sendgrid.helpers.mail.mail import Email
from sendgrid.helpers.mail.mail import Content
from sendgrid.helpers.mail.mail import Mail
from sendgrid.helpers.mail.mail import Attachment
from sendgrid.helpers.mail.mail import Personalization


def create_email(address, subject, template_name, context, attachment_filenames):
    templateLoader = jinja2.FileSystemLoader(searchpath="templates")
    templateEnv = jinja2.Environment(loader=templateLoader)
    html_template = templateEnv.get_template(template_name + ".html")

    html_to_send = html_template.render(context)

    impactstory_email = Email("team@impactstory.org", "Impactstory Team")
    to_email = Email(address)
    content = Content("text/html", html_to_send)
    email = Mail(impactstory_email, subject, to_email, content)
    personalization = Personalization()
    personalization.add_to(to_email)
    personalization.add_to(impactstory_email)
    email.add_personalization(personalization)

    if re.findall(u"[a-zA-Z0-9]{7,15}@gmail.com", address) and re.findall(u"[0-9]{2,}", address):
        email = Mail(impactstory_email, "Over limit. Please email us at team@impactstory.org for other data access options.", to_email, content)
        personalization = Personalization()
        personalization.add_to(to_email)
        # personalization.add_to(impactstory_email)
        email.add_personalization(personalization)
    else:
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
        response = sg.client.mail.send.post(request_body=email.get())
        print u"Sent an email"
    else:
        print u"Didn't really send"



