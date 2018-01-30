import os
import jinja2
import sendgrid
from sendgrid.helpers.mail.mail import Email
from sendgrid.helpers.mail.mail import Content
from sendgrid.helpers.mail.mail import Mail

def send(address, subject, template_name, context, attachment=None, for_real=False):

    templateLoader = jinja2.FileSystemLoader(searchpath="templates")
    templateEnv = jinja2.Environment(loader=templateLoader)
    html_template = templateEnv.get_template(template_name + ".html")

    html_to_send = html_template.render(context)

    sg = sendgrid.SendGridAPIClient(apikey=os.environ.get('SENDGRID_API_KEY'))
    from_email = Email("team@impactstory.org", "Impactstory Team")
    to_email = Email(address)
    content = Content("text/html", html_to_send)
    mail = Mail(from_email, subject, to_email, content)

    if for_real:
        response = sg.client.mail.send.post(request_body=mail.get())
        print u"Sent an email to {}".format(address)
    else:
        print u"Didn't really send"



