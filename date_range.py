from sqlalchemy.dialects.postgresql import JSONB
from executor import execute
import requests
from time import time
import datetime
import shortuuid
from urllib import quote
import os
import re
import geoip2.webservice

from app import logger
from app import db
from util import elapsed
from util import safe_commit
from util import clean_doi
from util import normalize_title
from pub import Pub


# CREATE TABLE doi_queue_dates as (select s as id, random() as rand, false as enqueued, null::timestamp as finished, null::timestamp as started, null::text as dyno FROM generate_series
#         ( '1980-01-01'::timestamp
#         , '2017-08-22'::timestamp
#         , '1 day'::interval) s);

# truncate doi_queue_dates
# insert into doi_queue_dates (select s as id, random() as rand, false as enqueued, null::timestamp as finished, null::timestamp as started, null::text as dyno FROM generate_series
#         ( '1950-01-01'::timestamp
#         , '2017-10-08'::timestamp
#         , '1 day'::interval) s);


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

    # def get_pmh_events(self, rows=100):
    #     urls = [
    #     "http://www.lareferencia.info:8080/oai/provider",
    #     "http://oai.bnf.fr/oai2/OAIHandler",
    #     "http://digitallibrary.usc.edu/oai/oai.php",
    #     "https://kuscholarworks.ku.edu/dspace-oai/request",
    #     "http://discovery.ucl.ac.uk/cgi/oai2",
    #     "http://www.diva-portal.org/dice/oai",
    #     "http://dlisv03.media.osaka-cu.ac.jp/il/oai_repository/repository",
    #     # "http://dspace.library.uu.nl/oai/request",
    #     "http://oai.persee.fr/c/ext/prescript/oai"
    #
    #         # "http://cds.cern.ch/oai2d",
    #         # "https://api.archives-ouvertes.fr/oai/hal",
    #         # "https://oai.datacite.org/oai",
    #         # "http://deepblue.lib.umich.edu/dspace-oai/request",
    #         # "https://depot.erudit.org/dspace-oai/request",
    #         # "http://www.econstor.eu/dspace-oai/request",
    #         # "http://oai.openedition.org",
    #         # "http://digital.csic.es/dspace-oai/request",
    #         # "http://texashistory.unt.edu/oai/",
    #         # "http://www.intechopen.com/oai/?",
    #         # "http://quod.lib.umich.edu/cgi/o/oai/oai",
    #         # "http://eprints.whiterose.ac.uk/cgi/oai2",
    #         # "http://ora.ox.ac.uk/oai",
    #         # "http://www.acervodigital.unesp.br/oai/request",
    #         # "http://authors.library.caltech.edu/cgi/oai2",
    #         # "http://pubman.mpdl.mpg.de/escidoc-oaiprovider/",
    #         # "http://dash.harvard.edu/oai/request",
    #         # "http://ir.lib.ntust.edu.tw/dspace-oai/request",
    #         # "https://biblio.ugent.be/oai",
    #         # "https://spiral.imperial.ac.uk/dspace-oai/request",
    #         # "http://orbit.dtu.dk/ws/oai",
    #         # "http://ntrs.nasa.gov/oai",
    #         # "https://www.repository.cam.ac.uk/oai/request",
    #         # "http://infoscience.epfl.ch/oai2d/",
    #         # "http://digitalcommons.unl.edu/do/oai/",
    #         # "http://www.zora.uzh.ch/cgi/oai2",
    #         # "http://dspace.mit.edu/oai/request"
    #         # "http://export.arxiv.org/oai2",
    #         # "https://www.ncbi.nlm.nih.gov/pmc/oai/oai.cgi",
    #         # "http://citeseerx.ist.psu.edu/oai2"
    #
    #         # "http://oai.repec.openlib.org/",
    #         # "http://oai.dtic.mil/oai/oai",
    #
    #     ]
    #
    #     for url in urls:
    #         logger.info(u"starting with url: {}, first={}, last={}".format(url, self.first_day, self.last_day))
    #         call_pmh_endpoint(url=url, first=self.first_day, last=self.last_day)
    #         logger.info(u"ending with url: {}, first={}, last={}".format(url, self.first_day, self.last_day))


    def get_unpaywall_events(self, rows=100):
        insights_client = geoip2.webservice.Client(os.getenv("MAXMIND_CLIENT_ID"), os.getenv("MAXMIND_API_KEY"))

        tar_gz_filename = "today-{}.tsv.gz".format(self.first_day)

        execute("rm {}".format(tar_gz_filename), check=False)  # clear it if there is already one there
        command_template = """curl --no-include -o {} -L -H "X-Papertrail-Token: {}" https://papertrailapp.com/api/v1/archives/{}/download"""

        command = command_template.format(tar_gz_filename, os.getenv("PAPERTRAIL_API_KEY"), self.first_day)
        execute(command)
        if execute("ls -lh {}".format(tar_gz_filename), check=False):
            execute("zgrep email=unpaywall@impactstory.org {} > unpaywall_events.txt".format(tar_gz_filename), capture=True, check=False)

        else:
            # no file.  get the files for all the hours instead
            execute("rm unpaywall_events.txt", check=False)  # clear it if there is already one there, because appending
            for hour in range(24):
                day_with_hour = "{}-{:02d}".format(self.first_day, hour)
                command = command_template.format(tar_gz_filename, os.getenv("PAPERTRAIL_API_KEY"), day_with_hour)
                execute(command)
                execute("zgrep email=unpaywall@impactstory.org {} >> unpaywall_events.txt".format(tar_gz_filename), capture=True, check=False)


        # writing into database

        fh = open("unpaywall_events.txt", "r")
        if execute("ls -lh unpaywall_events.txt", check=False):
            num_this_loop = 0
            for line in fh:
                #only keep lines that are the right kind of log lines
                if line and not (u"?email=unpaywall@impactstory.org" in line and
                                         u'\toadoi\t' in line and
                                         u'\theroku/router\t' in line and
                                         u'at=info method=GET path="/10' in line):
                    continue

                columns = line.split("\t")
                collected = columns[1]
                if not collected.startswith("20"):
                    # not a valid timestamp, skip this line
                    continue

                # at=info method=GET path="/10.1177_1073858413514136?email=unpaywall@impactstory.org" host=api.oadoi.org request_id=7ae3022c-0dcd-44b7-ae7e-a888d8843d4f fwd="70.666.777.999" dyno=web.6 connect=1ms service=40ms status=200 bytes=774 protocol=https \n
                try:
                    doi = re.findall('path="/(.*)\?email=unpaywall@impactstory.org', line)[0]
                    doi = doi.lower()
                    id = re.findall('request_id=(.*?) ', line)[0]
                    ip = re.findall('fwd="(.*)"', line)[0]
                except IndexError:
                    # skip this line, it doesn't have a doi or ip or whatever, continue to next line
                    continue

                # print collected, doi, ip, id
                unpaywall_obj = UnpaywallEvent(doi=doi, ip=ip, collected=collected)
                db.session.merge(unpaywall_obj)
                insights = IpInsights.query.filter(IpInsights.ip==ip).first()
                if not insights:
                    try:
                        response_insights = insights_client.insights(ip)
                    except ValueError:
                        # this is what it throws if bad ip address
                        response_insights = None

                    if response_insights:
                        insight_dict = response_insights.raw
                        for key in ["city", "country", "continent", "registered_country"]:
                            if key in insight_dict and  "names" in insight_dict[key]:
                                insight_dict[key]["name"] = insight_dict[key]["names"]["en"]
                                del insight_dict[key]["names"]
                        for key in ["subdivisions"]:
                            if key in insight_dict:
                                my_list = []
                                for item in insight_dict[key]:
                                    if "names" in item:
                                        item["name"] = item["names"]["en"]
                                        del item["names"]
                                my_list.append(item)
                                insight_dict[key] = my_list
                        insights = IpInsights(ip=ip, insights=insight_dict)
                        db.session.merge(insights)

                    num_this_loop += 1

                    if num_this_loop > rows:
                        logger.info(u"committing")
                        safe_commit(db)
                        num_this_loop = 0

        logger.info(u"done everything, saving last ones")
        safe_commit(db)


    def save_new_dois(self, rows=1000):
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
            # logger.info(u"calling url: {}".format(url))

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
                my_pub = Pub(id=doi, crossref_api_raw_new=api_raw)
                my_pub.title = my_pub.crossref_title
                # my_pub.normalized_title = normalize_title(my_pub.title)

                my_pub.update()
                db.session.merge(my_pub)
                num_between_commits += 1
                num_so_far += 1

                if num_between_commits > 100:
                    # logger.info(u"committing")
                    start_commit = time()
                    safe_commit(db)
                    logger.info(u"committing done in {} seconds".format(elapsed(start_commit, 2)))
                    num_between_commits = 0

            # logger.info(u"at bottom of loop, got {} records".format(len(resp_data["items"])))

        # make sure to get the last ones
        logger.info(u"done everything, saving last ones")
        safe_commit(db)
        return num_so_far

    def __repr__(self):
        return u"<DateRange (starts: {})>".format(self.id)





class UnpaywallEvent(db.Model):
    id = db.Column(db.Text, primary_key=True)
    doi = db.Column(db.Text)
    collected = db.Column(db.DateTime)
    updated = db.Column(db.DateTime)
    ip = db.Column(db.Text)

    def __init__(self, **kwargs):
        self.id = shortuuid.uuid()[0:20]
        self.updated = datetime.datetime.utcnow()
        super(UnpaywallEvent, self).__init__(**kwargs)


class IpInsights(db.Model):
    id = db.Column(db.Text, primary_key=True)
    ip = db.Column(db.Text)
    insights = db.Column(JSONB)
    updated = db.Column(db.DateTime)

    def __init__(self, **kwargs):
        self.id = shortuuid.uuid()[0:20]
        self.updated = datetime.datetime.utcnow()
        super(IpInsights, self).__init__(**kwargs)
