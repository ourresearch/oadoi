from util import elapsed
from time import time
from collections import defaultdict

import requests
import json
import re


def call_orcid_api(url):
    headers = {'Accept': 'application/orcid+json'}
    start = time()
    r = requests.get(url, headers=headers)
    print "got ORCID results in {elapsed}s for {url}".format(
        url=url,
        elapsed=elapsed(start)
    )
    orcid_resp_dict = r.json()
    return orcid_resp_dict


def get_orcid_api_raw_profile(id):
    url = "https://pub.orcid.org/v1.2/{id}/orcid-profile".format(id=id)
    orcid_resp_dict = call_orcid_api(url)
    return orcid_resp_dict["orcid-profile"]

def get_orcid_api_raw_affiliations(id):
    url = "https://pub.orcid.org/v1.2/{id}/affiliations".format(id=id)
    orcid_resp_dict = call_orcid_api(url)
    return orcid_resp_dict

def get_orcid_api_raw_funding(id):
    url = "https://pub.orcid.org/v1.2/{id}/funding".format(id=id)
    orcid_resp_dict = call_orcid_api(url)
    return orcid_resp_dict


def search_orcid(given_names, family_name):
    url = u"https://orcid.org/v1.2/search/orcid-bio/?q=given-names%3A{given_names}%20AND%20family-name%3A{family_name}&rows=100".format(
        given_names=given_names,
        family_name=family_name
    )
    orcid_resp_dict = call_orcid_api(url)
    ids = []
    ret = []
    for result in orcid_resp_dict["orcid-search-results"]["orcid-search-result"]:
        id = result["orcid-profile"]["orcid-identifier"]["path"]
        ids.append(id)
        orcid_profile = OrcidProfile(id)
        orcid_profile.name_is_distinct = orcid_profile.has_different_name(given_names, family_name)
        ret.append(orcid_profile.to_dict())

    return ret


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
        self.api_raw_profile = get_orcid_api_raw_profile(id)
        self.api_raw_affilations = get_orcid_api_raw_affiliations(id)
        self.api_raw_funding = get_orcid_api_raw_funding(id)
        self.name_is_distinct = False

    @property
    def id(self):
        try:
            return self.api_raw_profile["orcid-identifier"]["path"]
        except (TypeError,):
            return None

    @property
    def given_names(self):
        try:
            return self.api_raw_profile["orcid-bio"]["personal-details"]["given-names"]["value"]
        except (KeyError, TypeError,):
            return None

    @property
    def family_name(self):
        try:
            return self.api_raw_profile["orcid-bio"]["personal-details"]["family-name"]["value"]
        except (KeyError, TypeError,):
            return None

    @property
    def credit_name(self):
        try:
            return self.api_raw_profile["orcid-bio"]["personal-details"]["credit-name"]["value"]
        except (KeyError, TypeError,):
            return None

    @property
    def other_names(self):
        try:
            return self.api_raw_profile["orcid-bio"]["personal-details"]["other-names"]["value"]
        except (KeyError, TypeError,):
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
    def recent_work(self):
        if not self.works:
            return None

        return self.works[0]["work-title"]["title"]["value"]


    @property
    def best_affiliation(self):
        return get_most_recently_ended_activity(self.affiliations)


    @property
    def affiliations(self):
        ret = []
        try:
            affiliation_list = self.api_raw_affilations["orcid-profile"]["orcid-activities"]["affiliations"]["affiliation"]
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
                "affl_name": affl_name, 
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
            funding_list = self.api_raw_funding["orcid-profile"]["orcid-activities"]["funding-list"]["funding"]
        except (TypeError, ):
            return ret

        for fund in funding_list:
            fund_name = fund["organization"]["name"]
            title = fund["funding-title"]["title"]["value"]
            amount = fund["amount"]
            try:
                end_year = int(fund["end-date"]["year"]["value"])
            except (KeyError, TypeError,):
                end_year = None
            ret.append({
                "fund_name": fund_name, 
                "title": title, 
                "amount": amount, 
                "end_year": end_year
                })
        return ret

    @property
    def api_raw(self):
        return self.api_raw_profile




    def __repr__(self):
        return u'<OrcidProfile ({id}) "{given_names} {family_name}" >'.format(
            id=self.id,
            given_names=self.given_names,
            family_name=self.family_name
        )

    def to_dict(self):
        return {
            "id": self.id,
            "given_names": self.given_names,
            "family_name": self.family_name,
            "credit_name": self.credit_name,
            "other_names": self.other_names,
            "best_funding": self.best_funding,
            "best_affiliation": self.best_affiliation,
            "recent_work": self.recent_work,
            "name_is_distinct": self.name_is_distinct,
            "num_works": len(self.works)
        }









def get_id_clues_for_orcid_search_result(result_dict):
    bio = result_dict["orcid-profile"]["orcid-bio"]

    ret = {
        "id": result_dict["orcid-profile"]["orcid-identifier"]["path"],
        "given_names": bio["personal-details"]["given-names"]["value"],
        "family_name": bio["personal-details"]["family-name"]["value"]
    }

    try:
        ret["keywords"] = bio["keywords"]["keyword"][0]["value"]
    except TypeError:
        ret["keywords"] = None


    # we could return early here if we want to be efficient.

    # get the latest article
    orcid_record = OrcidProfile(ret["id"])

    # in the future, we do things to get the articles
    works = orcid_record.works

    # for future: sort works by date
    pass

    try:
        ret["latest_article"] = works[0]["work-title"]["title"]["value"]
    except IndexError:
        pass

    ret["sortValue"] = len(ret.keys())

    return ret








