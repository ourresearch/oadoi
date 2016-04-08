import mandrill
import os
import logging
import jinja2


logger = logging.getLogger("emailer")

def send(address, subject, template_name, context):

    templateLoader = jinja2.FileSystemLoader(searchpath="templates")
    templateEnv = jinja2.Environment(loader=templateLoader)
    html_template = templateEnv.get_template(template_name + ".html")

    html_to_send = html_template.render(context)

    mailer = mandrill.Mandrill(os.getenv("MANDRILL_APIKEY"))

    addressee = {"email": address}
    try:
        addressee["name"] = context["name"]
    except KeyError:
        pass


    msg = {
        "html": html_to_send,
        "subject": subject,
        "from_email": "team@impactstory.org",
        "from_name": "The Impactstory team",
        "to": [addressee],  # must be a list
        "track_opens": True,
        "track_clicks": True
    }

    try:
        msg["tags"] = context["tags"]
    except KeyError:
        pass

    mailer.messages.send(msg)
    logger.info(u"Sent an email to " + address)

    return msg


