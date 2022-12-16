from app import db

import re
from urllib.parse import urlparse


class HostNameToConvert(db.Model):
    """Model for domains to convert all URLs from http to https."""
    __tablename__ = 'convert_http_to_https'

    id = db.Column(db.Integer, primary_key=True)
    hostname = db.Column(db.Text, unique=True)


def fix_url_scheme(url):
    if not url:
        return url

    sub_https = False

    hostname = urlparse(url).hostname

    if hostname in [
        'revista-iberoamericana.pitt.edu',
        'www.spandidos-publications.com',
        'olh.openlibhums.org',
        'jmla.pitt.edu',
        'jwsr.pitt.edu',
        'www.cs-ophthalmology.cz',
        'cs-ophthalmology.cz',
        'rua.ua.es',
        'cdr.lib.unc.edu',
        'www.hippiatrika.com',
        'www.macrothink.org',
        'psyarxiv.com',
        'osf.io',
        'journals.openedition.org',
        'jyd.pitt.edu',
        'apcz.umk.pl',
        'www.ccrjournal.com',
        'europepmc.org',
        'www.psychologicabelgica.com',
        'insights.uksg.org',
        'www.sjweh.fi',
        'dspace.library.uu.nl',
        'redfame.com',
        'www.ccsenet.org',
        'www.iieta.org',
        'jurnal.asmtb.ac.id',
        'journals.linguisticsociety.org',
        'publicatio.bibl.u-szeged.hu',
        'edarxiv.org'
    ]:
        sub_https = True

    if url.startswith('http://hdl.handle.net/10871/'):
        sub_https = True

    if sub_https:
        url = re.sub(r'^http://', 'https://', url)

    # look up hostname in database
    hostname_to_convert = HostNameToConvert.query.filter_by(hostname=hostname).first()
    if hostname_to_convert:
        url = re.sub(r'^http://', 'https://', url)

    return url
