from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import deferred
from sqlalchemy import or_
from sqlalchemy import sql
from sqlalchemy import text
from sqlalchemy import orm
import requests
from time import sleep
from time import time
import datetime
import shortuuid
from urllib import quote

from app import logger
from app import db
from util import elapsed
from util import safe_commit
from util import clean_doi


class DateRange(db.Model):
    id = db.Column(db.DateTime, primary_key=True)
    # end_date = db.Column(db.DateTime)

    @property
    def first(self):
        return self.id

    @property
    def first_day(self):
        return self.id.isoformat()[0:10]

    @property
    def last_day(self):
        return self.last.isoformat()[0:10]

    @property
    def last(self):
        return self.first + datetime.timedelta(days=1)

    def get_crossref_api_raw(self, rows=100):
        headers={"Accept": "application/json", "User-Agent": "impactstory.org"}
        base_url_with_last = "http://api.crossref.org/works?filter=from-created-date:{first},until-created-date:{last}&rows={rows}&cursor={next_cursor}"
        # but if want all changes, use "indexed" not "created" as per https://github.com/CrossRef/rest-api-doc/blob/master/rest_api.md#notes-on-incremental-metadata-updates

        next_cursor = "*"
        has_more_responses = True
        num_so_far = 0
        num_between_commits = 0

        while has_more_responses:
            start_time = time()
            url = base_url_with_last.format(
                first=self.first_day,
                last=self.last_day,
                rows=rows,
                next_cursor=next_cursor)
            logger.info(u"calling url: {}".format(url))

            resp = requests.get(url, headers=headers)
            logger.info(u"getting crossref response took {} seconds".format(elapsed(start_time, 2)))
            if resp.status_code != 200:
                logger.info(u"error in crossref call, status_code = {}".format(resp.status_code))
                return

            resp_data = resp.json()["message"]
            next_cursor = resp_data.get("next-cursor", None)
            if next_cursor:
                next_cursor = quote(next_cursor)

            if not resp_data["items"] or not next_cursor:
                has_more_responses = False

            for api_raw in resp_data["items"]:
                doi = clean_doi(api_raw["DOI"])
                crossref_api_obj = CrossrefApi(doi=doi, api_raw=api_raw)
                db.session.add(crossref_api_obj)
                num_between_commits += 1
                num_so_far += 1

                if num_between_commits > 100:
                    safe_commit(db)
                    num_between_commits = 0

            logger.info(u"at bottom of loop, got {} records".format(len(resp_data["items"])))

        # make sure to get the last ones
        logger.info(u"done everything, saving last ones")
        safe_commit(db)
        return num_so_far

    def __repr__(self):
        return u"<DateRange (starts: {})>".format(self.id)


class CrossrefApi(db.Model):
    id = db.Column(db.Text, primary_key=True)
    doi = db.Column(db.Text)
    updated = db.Column(db.DateTime)
    api_raw = db.Column(JSONB)

    def __init__(self, **kwargs):
        self.id = shortuuid.uuid()[0:10]
        self.updated = datetime.datetime.utcnow()
        super(CrossrefApi, self).__init__(**kwargs)
