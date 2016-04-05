from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import deferred
from collections import defaultdict
import langdetect
import json
import shortuuid
import requests
import os
import re
import logging
import iso8601
import pytz

from app import db
from util import remove_nonprinting_characters
from util import days_ago
from util import days_between

from models.source import sources_metadata
from models.source import Source
from models.country import country_info
from models.country import get_name_from_iso
from models.language import get_language_from_abbreviation
from models.doaj import doaj_issns


class NoDoiException(Exception):
    pass

def make_product(orcid_product_dict):
    product = Product(id=shortuuid.uuid()[0:10])

    # get the DOI
    dirty_doi = None
    type = None

    if "work-type" in orcid_product_dict:
        type = str(orcid_product_dict['work-type'].encode('utf-8')).lower()
    if orcid_product_dict.get('work-external-identifiers', []):
        for x in orcid_product_dict.get('work-external-identifiers', []):
            for eid in orcid_product_dict['work-external-identifiers']['work-external-identifier']:
                if eid['work-external-identifier-type'] == 'DOI':
                    dirty_doi = str(eid['work-external-identifier-id']['value'].encode('utf-8')).lower()

    product.doi = clean_doi(dirty_doi)  # throws error unless valid DOI
    product.type = type

    product.api_raw = json.dumps(orcid_product_dict)
    return product


def clean_doi(dirty_doi):
    if not dirty_doi:
        raise NoDoiException("There's no valid DOI.")

    dirty_doi = remove_nonprinting_characters(dirty_doi)
    dirty_doi = dirty_doi.strip()

    # test cases for this regex are at https://regex101.com/r/zS4hA0/1
    p = re.compile(ur'.*?(10.+)')

    matches = re.findall(p, dirty_doi)
    if len(matches) == 0:
        raise NoDoiException("There's no valid DOI.")

    match = matches[0]

    try:
        resp = unicode(match, "utf-8")  # unicode is valid in dois
    except (TypeError, UnicodeDecodeError):
        resp = match

    # remove any url fragments
    if u"#" in resp:
        resp = resp.split(u"#")[0]

    return resp





class Product(db.Model):
    id = db.Column(db.Text, primary_key=True)
    doi = db.Column(db.Text)
    orcid_id = db.Column(db.Text, db.ForeignKey('person.orcid_id'))

    title = db.Column(db.Text)
    journal = db.Column(db.Text)
    type = db.Column(db.Text)
    pubdate = db.Column(db.DateTime)
    year = db.Column(db.Text)
    authors = db.Column(db.Text)

    api_raw = db.Column(db.Text)  #orcid
    crossref_api_raw = deferred(db.Column(JSONB))
    altmetric_api_raw = deferred(db.Column(JSONB))

    altmetric_id = db.Column(db.Text)
    altmetric_score = db.Column(db.Float)
    post_counts = db.Column(MutableDict.as_mutable(JSONB))
    post_details = db.Column(MutableDict.as_mutable(JSONB))
    tweeter_details = db.Column(MutableDict.as_mutable(JSONB))
    poster_counts = db.Column(MutableDict.as_mutable(JSONB))
    event_dates = db.Column(MutableDict.as_mutable(JSONB))

    in_doaj = db.Column(db.Boolean)

    error = db.Column(db.Text)


    def set_data_from_crossref(self, high_priority=False):
        # set_altmetric_api_raw catches its own errors, but since this is the method
        # called by the thread from Person.set_data_from_crossref
        # want to have defense in depth and wrap this whole thing in a try/catch too
        # in case errors in calculate_metrics or anything else we add.
        try:
            self.set_crossref_api_raw(high_priority)
            self.set_biblio_from_crossref()
        except (KeyboardInterrupt, SystemExit):
            # let these ones through, don't save anything to db
            raise
        except Exception:
            logging.exception("exception in set_data_from_crossref")
            self.error = "error in set_data_from_crossref"
            print self.error
            print u"in generic exception handler, so rolling back in case it is needed"
            db.session.rollback()



    def set_biblio_from_crossref(self):
        try:
            biblio_dict = self.crossref_api_raw

            # if "type" in biblio_dict:
            #     self.type = biblio_dict["type"]

            # replace many white spaces and \n with just one space
            if "title" in biblio_dict:
                self.title = re.sub(u"\s+", u" ", biblio_dict["title"])

            if "container-title" in biblio_dict:
                self.journal = biblio_dict["container-title"]
            elif "publisher" in biblio_dict:
                self.journal = biblio_dict["publisher"]

            if "authors" in biblio_dict:
                self.authors = ", ".join(biblio_dict["authors"])
            if "pubdate" in biblio_dict:
                self.pubdate = iso8601.parse_date(biblio_dict["pubdate"]).replace(tzinfo=None)
            else:
                self.pubdate = iso8601.parse_date(biblio_dict["first_seen_on"]).replace(tzinfo=None)
            self.year = self.pubdate.year
        except (KeyError, TypeError):
            # doesn't always have citation (if error)
            # and sometimes citation only includes the doi
            pass

    def set_data_from_altmetric(self, high_priority=False):
        # set_altmetric_api_raw catches its own errors, but since this is the method
        # called by the thread from Person.set_data_from_altmetric_for_all_products
        # want to have defense in depth and wrap this whole thing in a try/catch too
        # in case errors in calculate_metrics or anything else we add.
        try:
            self.set_altmetric_api_raw(high_priority)
            self.calculate_metrics()
        except (KeyboardInterrupt, SystemExit):
            # let these ones through, don't save anything to db
            raise
        except Exception:
            logging.exception("exception in set_data_from_altmetric")
            self.error = "error in set_data_from_altmetric"
            print self.error
            print u"in generic exception handler, so rolling back in case it is needed"
            db.session.rollback()


    def calculate_metrics(self):
        self.set_biblio_from_altmetric()
        self.set_altmetric_score()
        self.set_altmetric_id()
        self.set_post_counts()
        self.set_poster_counts()
        self.set_post_details()
        self.set_tweeter_details
        self.set_event_dates()
        self.set_in_doaj()




    def set_biblio_from_altmetric(self):
        try:
            biblio_dict = self.altmetric_api_raw["citation"]
            self.title = biblio_dict["title"]
            self.journal = biblio_dict["journal"]
            if "authors" in biblio_dict:
                self.authors = ", ".join(biblio_dict["authors"])
            # self.type = biblio_dict["type"]  get type from ORCID instead
            if "pubdate" in biblio_dict:
                self.pubdate = iso8601.parse_date(biblio_dict["pubdate"]).replace(tzinfo=None)
            else:
                self.pubdate = iso8601.parse_date(biblio_dict["first_seen_on"]).replace(tzinfo=None)
            self.year = self.pubdate.year
        except (KeyError, TypeError):
            # doesn't always have citation (if error)
            # and sometimes citation only includes the doi
            pass


    def set_altmetric_score(self):
        self.altmetric_score = 0
        try:
            self.altmetric_score = self.altmetric_api_raw["score"]
            # print u"set score to", self.altmetric_score
        except (KeyError, TypeError):
            pass

    def get_abstract(self):
        try:
            abstract = self.altmetric_api_raw["citation"]["abstract"]
        except (KeyError, TypeError):
            abstract = None
        return abstract


    def post_counts_by_source(self, source):
        if not self.post_counts:
            return 0

        if source in self.post_counts:
            return self.post_counts[source]
        return 0

    @property
    def posts(self):
        if self.post_details and "list" in self.post_details:
            return self.post_details["list"]
        return []

    def set_post_details(self):
        if not self.altmetric_api_raw or \
                ("posts" not in self.altmetric_api_raw) or \
                (not self.altmetric_api_raw["posts"]):
            return

        all_post_dicts = []

        for (source, posts) in self.altmetric_api_raw["posts"].iteritems():
            for post in posts:
                post_dict = {}
                post_dict["source"] = source

                if source == "twitter":
                    if "author" in post:
                        if "id_on_source" in post["author"]:
                            post_dict["twitter_handle"] = post["author"]["id_on_source"]
                        if "followers" in post["author"]:
                            post_dict["followers"] = post["author"]["followers"]

                # useful parts
                if "posted_on" in post:
                    post_dict["posted_on"] = post["posted_on"]

                if "author" in post and "name" in post["author"]:
                    post_dict["attribution"] = post["author"]["name"]

                if "page_url" in post:
                    # for wikipedia.  we want this one not what is under url
                    post_dict["url"] = post["page_url"]
                elif "url" in post:
                    post_dict["url"] = post["url"]

                # title or summary depending on post type
                if source in ["blogs", "f1000", "news", "q&a", "reddit", "wikipedia"] and "title" in post:
                    post_dict["title"] = post["title"]
                    if source == "wikipedia" and "summary" in post:
                        post_dict["summary"] = post["summary"]
                elif "summary" in post:
                    title = post["summary"]
                    # remove urls.  From http://stackoverflow.com/a/11332580/596939
                    title = re.sub(r'^https?:\/\/.*[\r\n]*', '', title, flags=re.MULTILINE)
                    if not title:
                        title = "No title."
                    if len(title.split()) > 15:
                        first_few_words = title.split()[:15]
                        title = u" ".join(first_few_words)
                        title = u"{} \u2026".format(title)
                    post_dict["title"] = title
                else:
                    post_dict["title"] = ""

                all_post_dicts.append(post_dict)

        all_post_dicts = sorted(all_post_dicts, key=lambda k: k["posted_on"], reverse=True)
        all_post_dicts = sorted(all_post_dicts, key=lambda k: k["source"])

        self.post_details = {"list": all_post_dicts}
        return self.post_details

    def set_post_counts(self):
        self.post_counts = {}

        if not self.altmetric_api_raw or "counts" not in self.altmetric_api_raw:
            return

        exclude_keys = ["total", "readers"]
        for k in self.altmetric_api_raw["counts"]:
            if k not in exclude_keys:
                source = k
                count = int(self.altmetric_api_raw["counts"][source]["posts_count"])
                self.post_counts[source] = count
                # print u"setting posts for {source} to {count} for {doi}".format(
                #     source=source,
                #     count=count,
                #     doi=self.doi)


    def set_poster_counts(self):
        self.poster_counts = {}
        if not self.altmetric_api_raw or "counts" not in self.altmetric_api_raw:
            return

        exclude_keys = ["total", "readers"]
        for k in self.altmetric_api_raw["counts"]:
            if k not in exclude_keys:
                source = k
                count = int(self.altmetric_api_raw["counts"][source]["unique_users_count"])
                self.poster_counts[source] = count
                # print u"setting posters for {source} to {count} for {doi}".format(
                #     source=source,
                #     count=count,
                #     doi=self.doi)


    @property
    def tweeters(self):
        if self.tweeter_details and "list" in self.tweeter_details:
            return self.tweeter_details["list"]
        return []

    def set_tweeter_details(self):
        if not self.altmetric_api_raw or \
                ("posts" not in self.altmetric_api_raw) or \
                (not self.altmetric_api_raw["posts"]):
            return

        if not "twitter" in self.altmetric_api_raw["posts"]:
            return

        tweeter_dicts = {}

        for post in self.altmetric_api_raw["posts"]["twitter"]:
            twitter_handle = post["author"]["id_on_source"]

            if twitter_handle not in tweeter_dicts:
                tweeter_dict = {}
                tweeter_dict["url"] = u"http://twitter.com/{}".format(twitter_handle)

                if "name" in post["author"]:
                    tweeter_dict["name"] = post["author"]["name"]

                if "image" in post["author"]:
                    tweeter_dict["img"] = post["author"]["image"]

                if "description" in post["author"]:
                    tweeter_dict["description"] = post["author"]["description"]

                if "followers" in post["author"]:
                    tweeter_dict["followers"] = post["author"]["followers"]

                tweeter_dicts[twitter_handle] = tweeter_dict

        self.tweeter_details = {"list": tweeter_dicts.values()}


    @property
    def event_days_ago(self):
        if not self.event_dates:
            return {}
        resp = {}
        for source, date_list in self.event_dates.iteritems():
            resp[source] = [days_ago(event_date_string) for event_date_string in date_list]
        return resp

    @property
    def event_days_since_publication(self):
        if not self.event_dates or not self.pubdate:
            return {}
        resp = {}
        for source, date_list in self.event_dates.iteritems():
            resp[source] = [days_between(event_date_string, self.pubdate.isoformat()) for event_date_string in date_list]
        return resp

    def set_event_dates(self):
        self.event_dates = {}

        if not self.altmetric_api_raw or "posts" not in self.altmetric_api_raw:
            return
        if self.altmetric_api_raw["posts"] == []:
            return

        for source, posts in self.altmetric_api_raw["posts"].iteritems():
            for post in posts:
                post_date = post["posted_on"]
                if source not in self.event_dates:
                    self.event_dates[source] = []
                self.event_dates[source].append(post_date)

        # now sort them all
        for source in self.event_dates:
            self.event_dates[source].sort(reverse=False)
            # print u"set event_dates for {} {}".format(self.doi, source)


    def set_crossref_api_raw(self, high_priority=False):
        try:
            self.error = None

            # needs the vnd.citationstyles.csl for datacite dois like http://doi.org/10.5061/dryad.443t4m1q
            headers={"Accept": "application/vnd.citationstyles.csl+json", "User-Agent": "impactstory.org"}

            url = u"http://doi.org/{doi}".format(doi=self.clean_doi)

            # might throw requests.Timeout
            # print u"calling {} with headers {}".format(url, headers)
            r = requests.get(url, headers=headers, timeout=10)  #timeout in seconds

            if r.status_code == 404: # not found
                self.crossref_api_raw = {"error": "404"}
            elif r.status_code == 200:

                # we got a good status code!
                self.crossref_api_raw = r.json()
                # print u"yay crossref data for {doi}".format(doi=self.doi)
            else:
                self.error = u"got unexpected status_code code {}".format(r.status_code)

        except (KeyboardInterrupt, SystemExit):
            # let these ones through, don't save anything to db
            raise
        except requests.Timeout:
            self.error = "timeout error from requests when getting crossref data"
        except Exception:
            logging.exception("exception in set_crossref_api_raw")
            self.error = "misc error in set_crossref_api_raw"
            print u"in generic exception handler, so rolling back in case it is needed"
            db.session.rollback()
        finally:
            if self.error:
                print u"ERROR on {doi} profile {orcid_id}: {error}, calling {url}".format(
                    doi=self.clean_doi,
                    orcid_id=self.orcid_id,
                    error=self.error,
                    url=url)


    def set_altmetric_api_raw(self, high_priority=False):
        try:
            self.error = None

            url = u"http://api.altmetric.com/v1/fetch/doi/{doi}?key={key}".format(
                doi=self.clean_doi,
                key=os.getenv("ALTMETRIC_KEY")
            )
            # print u"calling {}".format(url)

            # might throw requests.Timeout
            r = requests.get(url, timeout=10)  #timeout in seconds

            # handle rate limit stuff
            if "x-hourlyratelimit-remaining" in r.headers:
                hourly_rate_limit_remaining = int(r.headers["x-hourlyratelimit-remaining"])
                if hourly_rate_limit_remaining != 3600:
                    print u"hourly_rate_limit_remaining=", hourly_rate_limit_remaining
            else:
                hourly_rate_limit_remaining = None

            if (hourly_rate_limit_remaining and (hourly_rate_limit_remaining < 500) and not high_priority) or \
                    r.status_code == 420:
                print u"sleeping for an hour until we have more calls remaining"
                sleep(60*60) # an hour

            # Altmetric.com doesn't have this DOI, so the DOI has no metrics.
            if r.status_code == 404:
                # altmetric.com doesn't have any metrics for this doi
                self.altmetric_api_raw = {"error": "404"}
            elif r.status_code == 403:
                if r.text == "You must have a commercial license key to use this call.":
                    # this is the error we get when we have a bad doi with a # in it.  Record, but don't throw error
                    self.altmetric_api_raw = {"error": "403. Altmetric.com says must have a commercial license key to use this call"}
                else:
                    self.error = 'got a 403 for unknown reasons'
            elif r.status_code == 420:
                self.error = "hard-stop rate limit error setting altmetric.com metrics"
            elif r.status_code == 400:
                self.altmetric_api_raw = {"error": "400. Altmetric.com says bad doi"}
            elif r.status_code == 200:
                # we got a good status code, the DOI has metrics.
                self.altmetric_api_raw = r.json()
                # print u"yay nonzero metrics for {doi}".format(doi=self.doi)
            else:
                self.error = u"got unexpected status_code code {}".format(r.status_code)

        except (KeyboardInterrupt, SystemExit):
            # let these ones through, don't save anything to db
            raise
        except requests.Timeout:
            self.error = "timeout error from requests when getting altmetric.com metrics"
        except Exception:
            logging.exception("exception in set_altmetric_api_raw")
            self.error = "misc error in set_altmetric_api_raw"
            print u"in generic exception handler, so rolling back in case it is needed"
            db.session.rollback()
        finally:
            if self.error:
                print u"ERROR on {doi} profile {orcid_id}: {error}, calling {url}".format(
                    doi=self.clean_doi,
                    orcid_id=self.orcid_id,
                    error=self.error,
                    url=url)

    def set_altmetric_id(self):
        try:
            self.altmetric_id = self.altmetric_api_raw["altmetric_id"]
        except (KeyError, TypeError):
            self.altmetric_id = None

    def set_in_doaj(self):
        self.in_doaj = False
        try:
            issns = self.crossref_api_raw["ISSN"]
            for issn in issns:
                if issn in doaj_issns:
                    self.in_doaj = True
            # print u"set in_doaj", self.in_doaj
        except (KeyError, TypeError):
            pass

    @property
    def is_open(self):
        return (self.is_oa_journal or self.is_oa_repository)

    @property
    def is_oa_journal(self):
        return self.in_doaj

    @property
    def is_oa_repository(self):
        doi_fragments = ["/npre.",
                         "/peerj.preprints",
                         ".figshare.",
                         "/dryad.",
                         "/zenodo.",
                         "/10.1101/"  #biorxiv
                         ]
        if any(fragment in self.doi for fragment in doi_fragments):
            return True
        return False

    @property
    def sources(self):
        sources = []
        for source_name in sources_metadata:
            source = Source(source_name, [self])
            if source.posts_count > 0:
                sources.append(source)
        return sources

    @property
    def events_last_week_count(self):
        events_last_week_count = 0
        for source in self.sources:
            events_last_week_count += source.events_last_week_count
        return events_last_week_count

    @property
    def display_title(self):
        if self.title:
            return self.title
        else:
            return "No title"

    @property
    def year_int(self):
        if not self.year:
            return 0
        return int(self.year)

    @property
    def countries(self):
        return [get_name_from_iso(my_country) for my_country in self.post_counts_by_country.keys()]

    @property
    def post_counts_by_country(self):
        try:
            resp = self.altmetric_api_raw["demographics"]["geo"]["twitter"]
        except (KeyError, TypeError):
            resp = {}
        return resp

    @property
    def poster_counts_by_type(self):
        try:
            resp = self.altmetric_api_raw["demographics"]["users"]["twitter"]["cohorts"]
            if not resp:
                resp = {}
        except (KeyError, TypeError):
            resp = {}
        return resp

    def has_source(self, source_name):
        if self.post_counts:
            return (source_name in self.post_counts)
        return False

    @property
    def impressions(self):
        return sum(self.twitter_posters_with_followers.values())


    def get_tweeter_posters_full_names(self, most_recent=None):
        names = []

        try:
            posts = self.altmetric_api_raw["posts"]["twitter"]
        except (KeyError, TypeError):
            return names

        if most_recent:
            posts = sorted(posts, key=lambda k: k["posted_on"], reverse=True)
            posts = posts[0:most_recent]
        for post in posts:
            try:
                names.append(post["author"]["name"])
            except (KeyError, TypeError):
                pass
        return names

    @property
    def follower_count_for_each_tweet(self):
        follower_counts = []
        try:
            twitter_posts = self.altmetric_api_raw["posts"]["twitter"]
        except (KeyError, TypeError):
            return {}

        for post in twitter_posts:
            try:
                poster = post["author"]["id_on_source"]
                followers = post["author"]["followers"]
                follower_counts.append(followers)
            except (KeyError, TypeError):
                pass
        return follower_counts

    @property
    def twitter_posters_with_followers(self):
        posters = {}
        try:
            twitter_posts = self.altmetric_api_raw["posts"]["twitter"]
        except (KeyError, TypeError):
            return {}

        for post in twitter_posts:
            try:
                poster = post["author"]["id_on_source"]
                followers = post["author"]["followers"]
                posters[poster] = followers
            except (KeyError, TypeError):
                pass
        return posters


    def f1000_urls_for_class(self, f1000_class):
        urls = []
        try:
            for post in self.altmetric_api_raw["posts"]["f1000"]:
                if f1000_class in post["f1000_classes"]:
                    urls.append(u"<a href='{}'>Review</a>".format(post["url"]))
        except (KeyError, TypeError):
            urls = []
        return urls

    @property
    def impact_urls(self):
        try:
            urls = self.altmetric_api_raw["citation"]["links"]
        except (KeyError, TypeError):
            urls = []
        return urls

    @property
    def languages_with_examples(self):
        resp = {}

        try:
            for (source, posts) in self.altmetric_api_raw["posts"].iteritems():
                for post in posts:
                    for key in ["title", "summary"]:
                        try:
                            num_words_in_post = len(post[key].split(" "))
                            top_detection = langdetect.detect_langs(post[key])[0]
                            if (num_words_in_post > 7) and (top_detection.prob > 0.90):

                                if top_detection.lang != "en":
                                    language_name = get_language_from_abbreviation(top_detection.lang)
                                    # print u"LANGUAGE:", language_name, top_detection.prob, post[key]

                                    # overwrites.  that's ok, we just want one example
                                    resp[language_name] = post["url"]

                        except langdetect.lang_detect_exception.LangDetectException:
                            pass

        except (KeyError, AttributeError, TypeError):
            pass

        return resp


    @property
    def publons_reviews(self):
        reviews = []
        try:
            for post in self.altmetric_api_raw["posts"]["peer_reviews"]:
                if post["pr_id"] == "publons":
                    reviews.append({
                        "url": post["publons_article_url"],
                        "publons_weighted_average": post["publons_weighted_average"]
                    })
        except (KeyError, TypeError):
            reviews = []
        return reviews

    @property
    def wikipedia_urls(self):
        articles = []
        try:
            for post in self.altmetric_api_raw["posts"]["wikipedia"]:
                articles.append(u"<a href='{}'>{}</a>".format(
                    post["page_url"],
                    post["title"]))
        except (KeyError, TypeError):
            articles = []
        return articles

    def has_country(self, country_name):
        return (country_name in self.countries)



    @property
    def clean_doi(self):
        # this shouldn't be necessary because we clean DOIs
        # before we put them in. however, there are a few legacy ones that were
        # not fully cleaned. this is to deal with them.
        return clean_doi(self.doi)

    def __repr__(self):
        return u'<Product ({id}) {doi}>'.format(
            id=self.id,
            doi=self.doi
        )

    # jason added this mock to test out genre icons on frontend
    def guess_genre(self):
        if self.title == "Facilitating Data-Intensive Ecology":
            return "slides"
        elif self.is_oa_repository:
            return "dataset"
        else:
            return "article"


    def to_dict(self):
        return {
            "id": self.id,
            "doi": self.doi,
            "orcid_id": self.orcid_id,
            "year": self.year,
            "title": self.title,
            "journal": self.journal,
            "authors": self.authors,
            "altmetric_id": self.altmetric_id,
            "altmetric_score": self.altmetric_score,
            "is_oa_journal": self.is_oa_journal,
            "is_oa_repository": self.is_oa_repository,
            "sources": [s.to_dict() for s in self.sources],
            "posts": self.posts,
            "events_last_week_count": self.events_last_week_count,

            # jason added this mock to test out genre icons on frontend
            "genre": self.guess_genre()
        }





