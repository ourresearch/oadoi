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

def send(address, subject, template_name, context, attachment=None, for_real=False):

    templateLoader = jinja2.FileSystemLoader(searchpath="templates")
    templateEnv = jinja2.Environment(loader=templateLoader)
    html_template = templateEnv.get_template(template_name + ".html")

    html_to_send = html_template.render(context)

    sg = sendgrid.SendGridAPIClient(apikey=os.environ.get('SENDGRID_API_KEY'))
    impactstory_email = Email("team@impactstory.org", "Impactstory Team")
    to_email = Email(address)
    content = Content("text/html", html_to_send)
    mail = Mail(impactstory_email, subject, to_email, content)
    personalization = Personalization()
    personalization.add_to(to_email)
    personalization.add_to(impactstory_email)
    mail.add_personalization(personalization)

    if attachment:
        my_attachment = Attachment()
        my_attachment.type = "application/csv"
        my_attachment.filename = "results.csv"
        my_attachment.disposition = "attachment"
        my_attachment.content_id = "results csv file"
        with open(attachment, 'rb') as f:
            data = f.read()

        #handle the spammer
        if re.findall(u"[a-z0-9]{7,15}@gmail.com", address):
            mail = Mail(impactstory_email, "Over limit. Please email us at team@impactstory.org for other data access options.", to_email, content)
            personalization = Personalization()
            personalization.add_to(to_email)
            personalization.add_to(impactstory_email)
            mail.add_personalization(personalization)
        else:
            my_attachment.content = base64.b64encode(data)


        mail.add_attachment(my_attachment)

    # if for_real:
    #     response = sg.client.mail.send.post(request_body=mail.get())
    #     print u"Sent an email to {}".format(address)
    # else:
    #     print u"Didn't really send"



