from time import time
from collections import defaultdict
import requests
import json
import re
from threading import Thread
from util import remove_nonprinting_characters

from util import elapsed

class NoOrcidException(Exception):
    pass

def clean_orcid(dirty_orcid):
    if not dirty_orcid:
        raise NoOrcidException("There's no valid orcid.")

    dirty_orcid = remove_nonprinting_characters(dirty_orcid)
    dirty_orcid = dirty_orcid.strip()

    # has to be digits, but last character of whole thing can be an X
    # because it is a checksum. as per http://support.orcid.org/knowledgebase/articles/116780-structure-of-the-orcid-identifier
    p = re.compile(ur'(\d{4}-\d{4}-\d{4}-\d{3}[\dX]{1})')

    matches = re.findall(p, dirty_orcid)
    if len(matches) == 0:
        raise NoOrcidException("There's no valid orcid.")

    return matches[0]


def call_orcid_api(url):
    headers = {'Accept': 'application/orcid+json'}
    start = time()

    # might throw requests.Timeout
    try:
        r = requests.get(url, headers=headers, timeout=10)
    except requests.Timeout:
        # do some error printing here, but let problem be handled further up the stack
        print u"requests.Timeout in call_orcid_api for url {}".format(url)
        raise

    # print "got ORCID results in {elapsed}s for {url}".format(
    #     url=url,
    #     elapsed=elapsed(start)
    # )
    orcid_resp_dict = r.json()
    return orcid_resp_dict


def get_orcid_api_raw_profile(id):
    url = "https://pub.orcid.org/v1.2/{id}/orcid-profile".format(id=id)
    orcid_resp_dict = call_orcid_api(url)
    return orcid_resp_dict["orcid-profile"]

# main constructor
def make_and_populate_orcid_profile(orcid_id):
    new_profile = OrcidProfile(orcid_id)
    new_profile.populate_from_orcid()
    return new_profile

# uses multithreaded approach from http://www.shanelynn.ie/using-python-threading-for-multiple-results-queue/
def build_and_return_orcid_profile(orcid_id, populated_profiles):
    new_profile = make_and_populate_orcid_profile(orcid_id)
    populated_profiles[orcid_id] = new_profile
    return populated_profiles

def make_and_populate_all_orcid_profiles(orcid_ids):
    threads = []
    populated_profiles = {}

    # start a thread for each orcid_id. results stored in populated_profiles.
    for orcid_id in orcid_ids:
        process = Thread(target=build_and_return_orcid_profile, args=[orcid_id, populated_profiles])
        process.start()
        threads.append(process)

    # wait till all work is done
    for process in threads:
        process.join()

    # return the results
    orcid_profile_list = populated_profiles.values()
    return orcid_profile_list




def search_orcid(given_names, family_name):
    url = u"https://orcid.org/v1.2/search/orcid-bio/?q=given-names%3A{given_names}%20AND%20family-name%3A{family_name}&rows=100".format(
        given_names=given_names,
        family_name=family_name
    )
    orcid_resp_dict = call_orcid_api(url)
    ret = []
    try:
        orcid_results = orcid_resp_dict["orcid-search-results"]["orcid-search-result"]
    except TypeError:
        return ret

    orcid_ids = []
    for result in orcid_results:
        orcid_id = result["orcid-profile"]["orcid-identifier"]["path"]
        orcid_ids.append(orcid_id)

    orcid_profile_list = make_and_populate_all_orcid_profiles(orcid_ids)

    for orcid_profile in orcid_profile_list:
        # before dumping the object to a dictionary, 
        # update this attribute based on the name we used to search for the orcid profile
        orcid_profile.has_name_variant_beyond_search_query = orcid_profile.has_only_this_name(given_names, family_name)
        orcid_profile_dict = orcid_profile.to_dict()
        ret.append(orcid_profile_dict)

    return sorted(ret, key=lambda k: k['sort_score'], reverse=True)


def get_most_recently_ended_activity(activities):
    if not activities:
        return None

    # if there are any without end dates, return them
    best = None
    for activity in activities:
        if not activity["end_year"]:
            best = activity  
    if best:
        return best

    # else return the one that has most recently ended
    return sorted(activities, key=lambda k: k['end_year'], reverse=True)[0]




class OrcidProfile(object):
    def __init__(self, id):
        self.id = id
        # initialize this to False.  Will be overwritten by calling search code if it
        # determines the 
        self.has_name_variant_beyond_search_query = False

    def populate_from_orcid(self):
        self.api_raw_profile = get_orcid_api_raw_profile(self.id)

    @property
    def given_names(self):
        try:
            return self.api_raw_profile["orcid-bio"]["personal-details"]["given-names"]["value"]
        except (KeyError, TypeError):
            return None

    @property
    def family_name(self):
        try:
            return self.api_raw_profile["orcid-bio"]["personal-details"]["family-name"]["value"]
        except (KeyError, TypeError):
            return None

    @property
    def credit_name(self):
        try:
            return self.api_raw_profile["orcid-bio"]["personal-details"]["credit-name"]["value"]
        except (KeyError, TypeError):
            return None

    @property
    def other_names(self):
        try:
            return self.api_raw_profile["orcid-bio"]["personal-details"]["other-names"]["value"]
        except (KeyError, TypeError):
            return None

    def has_only_this_name(self, given_names, family_name):
        given_names = given_names.lower().strip()
        family_name = family_name.lower().strip()

        full_name = u"{} {}".format(given_names, family_name)

        if self.given_names.lower().strip() != given_names:
            return True
        if self.family_name.lower().strip() != family_name:
            return True
        if self.credit_name and self.credit_name.lower().strip() != full_name:
            return True
        if self.other_names and self.other_names.lower().strip() != full_name:
            return True
        return False


    @property
    def biography(self):
        try:
            return self.api_raw_profile["orcid-bio"]["biography"]["value"]
        except (KeyError, TypeError):
            return None

    @property
    def researcher_urls(self):
        try:
            urls_dict = self.api_raw_profile["orcid-bio"]["researcher-urls"]["researcher-url"]
            if not urls_dict:
                urls_dict = None
            return urls_dict
        except (KeyError, TypeError):
            return None

    @property
    def keywords(self):
        try:
            return self.api_raw_profile["orcid-bio"]["keywords"]["keyword"][0]["value"]
        except (KeyError, TypeError):
            return None


    @property
    def works(self):
        try:
            works = self.api_raw_profile["orcid-activities"]["orcid-works"]["orcid-work"]
        except TypeError:
            works = None

        if not works:
            works = []
        return works


    @property
    def latest_work(self):
        if not self.works:
            return None

        latest_year = 0
        for work in self.works:
            try:
                year = int(work["publication-date"]["year"]["value"])
            except TypeError:
                # no year found
                continue

            if year > latest_year:
                best = work
                latest_year = year

        if not best:
            best = self.works[0]

        return best["work-title"]["title"]["value"]


    @property
    def best_affiliation(self):
        return get_most_recently_ended_activity(self.affiliations)


    @property
    def affiliations(self):
        ret = []
        try:
            affiliation_list = self.api_raw_profile["orcid-activities"]["affiliations"]["affiliation"]
        except (TypeError, ):
            return ret

        for affl in affiliation_list:
            affl_name = affl["organization"]["name"]
            role_title = affl["role-title"]
            try:
                end_year = int(affl["end-date"]["year"]["value"])
            except (KeyError, TypeError,):
                end_year = None
            ret.append({
                "name": affl_name, 
                "role_title": role_title, 
                "end_year": end_year
                })
        return ret

    @property
    def best_funding(self):
        return get_most_recently_ended_activity(self.funding)


    @property
    def funding(self):
        ret = []
        try:
            funding_list = self.api_raw_profile["orcid-activities"]["funding-list"]["funding"]
        except (TypeError, ):
            return ret

        for fund in funding_list:
            funder = fund["organization"]["name"]
            title = fund["funding-title"]["title"]["value"]
            try:
                end_year = int(fund["end-date"]["year"]["value"])
            except (KeyError, TypeError,):
                end_year = None
            ret.append({
                "funder": funder, 
                "title": title, 
                "end_year": end_year
                })
        return ret


    def __repr__(self):
        return u'<OrcidProfile ({id}) "{given_names} {family_name}" >'.format(
            id=self.id,
            given_names=self.given_names,
            family_name=self.family_name
        )

    def to_dict(self):
        search_clues_dict = {
            "credit_name": self.credit_name,
            "other_names": self.other_names,
            "keywords": self.keywords,
            "biography": self.biography,
            "researcher_urls": self.researcher_urls,
            "best_funding": self.best_funding,
            "best_affiliation": self.best_affiliation,
            "latest_work": self.latest_work,
            "has_name_variant_beyond_search_query": self.has_name_variant_beyond_search_query,
            "num_works": len(self.works)
        }

        search_clues_list = []
        for k, v in search_clues_dict.iteritems():
            if v:  # only return truthy values
                search_clues_list.append({"key":k, "value":v})

        ret = {
            "id": self.id,
            "given_names": self.given_names,
            "family_name": self.family_name,
            "search_clues_list": search_clues_list,
            "sort_score": len(search_clues_list)
        }

        return ret













