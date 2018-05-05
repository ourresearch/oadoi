import requests
import datetime
from time import time
from time import sleep
from sqlalchemy.dialects.postgresql import JSONB
from requests.packages.urllib3.util.retry import Retry

from app import db
from app import logger
from util import clean_doi
from util import safe_commit
from util import elapsed
from util import DelayedAdapter

class Chorus(db.Model):
    id = db.Column(db.Text, primary_key=True)
    updated = db.Column(db.DateTime)
    raw = db.Column(JSONB)

    def __init__(self, **kwargs):
        self.updated = datetime.datetime.utcnow()
        if "doi" in kwargs:
            kwargs["doi"] = clean_doi(kwargs["doi"])
        super(Chorus, self).__init__(**kwargs)

    def __repr__(self):
        return u"<Chorus ({})>".format(self.id)


def get_chorus_agency_ids():
    agencies_url = "https://api.chorusaccess.org/agencies/publicAccessPlan"
    r = requests.get(agencies_url)
    agencies = r.json()
    agency_ids = [agency["Agency_Id"] for agency in agencies]
    return agency_ids

def get_chorus_data():
    requests_session = requests.Session()
    retries = Retry(total=10,
                backoff_factor=0.5,
                status_forcelist=[500, 502, 503, 504])
    requests_session.mount('http://', DelayedAdapter(max_retries=retries))
    requests_session.mount('https://', DelayedAdapter(max_retries=retries))

    agency_ids = get_chorus_agency_ids()
    for agency_id in agency_ids:
        url_template = "https://api.chorusaccess.org/v1.1/agencies/{agency_id}/histories/current?category=publicly_accessible&limit={limit}&offset={offset}"
        offset = 0
        limit = 200
        total_results = None
        while total_results==None or offset < total_results:
            loop_start = time()
            url = url_template.format(agency_id=agency_id, offset=offset, limit=limit)
            print url
            r = requests_session.get(url, timeout=360)  # wait for 3 minutes
            print u"api call elapsed: {} seconds".format(elapsed(loop_start, 1))
            data = r.json()
            total_results = data["total_results"]
            # print data["agency_name"], "has", total_results, "results"
            items = data["items"]
            offset += limit
            new_objects = []
            for item in items:
                if item["DOI"]:
                    doi = clean_doi(item["DOI"])
                    new_objects.append(Chorus(id=doi, raw=item))

            ids_already_in_db = [id_tuple[0] for id_tuple in db.session.query(Chorus.id).filter(Chorus.id.in_([obj.id for obj in new_objects])).all()]
            objects_to_add_to_db = [obj for obj in new_objects if obj.id not in ids_already_in_db]
            if objects_to_add_to_db:
                logger.info(u"adding {} items".format(len(objects_to_add_to_db)))
                db.session.add_all(objects_to_add_to_db)
                safe_commit(db)
            else:
                logger.info(u"all of these items already in db")

            logger.info(u"sleeping for 2 seconds")
            sleep(2)


if __name__ == "__main__":
    get_chorus_data()

