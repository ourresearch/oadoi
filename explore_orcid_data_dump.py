import tarfile
import json
import datetime
import re
import time

from models import temp_orcid_profile
from models.temp_orcid_profile import TempOrcidProfile
from models.temp_product import TempProduct
from app import db

db.create_all()
db.session.commit()


def profile_summaries():

    num_profiles_to_commit = 0 
    start_time = time.time()

    orcids = TempOrcidProfile.query.all()
    print "Got all orcid profiles in {}sec".format(elapsed(start_time))
    start_time = time.time()

    for profile in orcids:

        id = profile.id
        # print "looking at", id

        profile_json = json.loads(profile.api_raw)
        profile.twitter = "none"
        profile.has_urls = False
        try:
            url_dicts = profile_json["researcher-urls"]["researcher-url"]
            for url_dict in url_dicts:
                profile.has_urls = True
                if "twitter.com" in url_dict["url"]["value"]:
                    profile.twitter = url_dict["url"]["value"]
                    print "**************added twitter", profile.twitter
        except KeyError:
            print ".",
        db.session.add(profile)
        num_profiles_to_commit += 1

        # try:
        #     bio = profile_json["orcid-bio"]["biography"]["value"]
        #     if bio:
        #         profile.has_bio = True
        #         print "**************added bio", profile.has_bio
        # except (TypeError,):
        #     pass

        # try:
        #     email = profile_json["contact-details"]["email"]
        #     if email:
        #         profile.has_email = True
        #         print "**************added bio", profile.has_bio
        # except (TypeError,):
        #     pass


        if num_profiles_to_commit % 100 == 0:
            print "COMMITTING"
            db.session.commit()
            print "did {} orcid profiles in {}s\n".format(
                num_profiles_to_commit, elapsed(start_time))

    # a last one to get any stragglers
    print "\n\nCOMMITTING\n\n"
    db.session.commit()


def store_dois():

    num_profiles_to_commit = 0 
    orcids = TempOrcidProfile.query.all()
    db.session.commit()

    for profile in orcids:

        id = profile.id
        if profile.products:
            print id, "already has products"
            continue

        profile_json = json.loads(profile.api_raw)
        works = profile_json["orcid-activities"]["orcid-works"]["orcid-work"]

        if not works:
            works = []

        # now go through and look at the works in more detail
        titles, dois, dois_since_2010 = [], [], []
        if works:

            for i, result in enumerate(works):

                try:
                    title = str(result['work-title']['title']['value'].encode('utf-8'))
                except TypeError:
                    title = ""
                doi = ""

                if result.get('work-external-identifiers', []):
                    for x in result.get('work-external-identifiers', []):
                        for eid in result['work-external-identifiers']['work-external-identifier']:
                            if eid['work-external-identifier-type'] == 'DOI':
                                doi = str(eid['work-external-identifier-id']['value'].encode('utf-8')).lower()

                # AIP journals tend to have a \n in the DOI, and the doi is the second line. we get
                # that here.
                if len(doi.split('\n')) == 2:
                    doi = doi.split('\n')[1]

                pub_date = result.get('publication-date', None)
                if pub_date:
                    year = pub_date.get('year', None).get('value').encode('utf-8')
                else:
                    year = 'Unknown'

                # Try to minimize duplicate entries that are found
                dup = False
                if (title and title.lower() in titles):
                    dup = True
                if (doi and doi in dois):
                    dup = True

                if not dup:
                    # truncate title to first 50 characters
                    print('| {3} | {0}  | {1} | [[doi:{2}]]|'.format(title[0:50], year, doi, result['work-type']))

                    if title:
                        titles.append(title.lower())
                    if doi:
                        dois.append(doi)
                        if year and year != 'Unknown' and int(year) > 2011:
                            dois_since_2010.append(doi)

                        created_date = datetime.datetime.fromtimestamp(result["created-date"]["value"]/1000).isoformat()
                        data_to_add = dict(
                            doi=doi, 
                            year=year,
                            title=title,
                            created=created_date,
                            work_type=result['work-type']
                            )
                        product = TempProduct(**data_to_add)
                        print "adding doi", doi, "to orcid", id
                        profile.products.append(product)


        print id

        print u"\n\nadded to db: {}".format(profile)
        num_profiles_to_commit += 1

        if num_profiles_to_commit > 100:
            print "\n\nCOMMITTING\n\n"
            db.session.commit()
            num_profiles_to_commit = 0 




def store_tar():

    num_profiles_to_commit = 0 
    # all_orcids = [row[0] for row in db.session.query(TempOrcidProfile.id).all()]
    # db.session.commit()

    tar = tarfile.open("/Users/hpiwowar/Downloads/orcid_data_dump.tar", 'r')
    for tar_info in tar:

        # # if already here, skip
        # try:
        #     orcid_id = re.match('\./json/(.*)\.json', tar_info.name).group(1)
        # except AttributeError:  # first file is called just "."
        #     continue

        # if orcid_id in all_orcids:
        #     print u"orcid {} in db already, skipping".format(orcid_id)
        #     continue

        # get contents of tar file
        fh = tar.extractfile(tar_info)
        if not fh:
            continue
        text = fh.read()
        if not text:
            continue

        # extract the orcid stuff we care about
        data_dict = json.loads(text)
        profile_dict = data_dict["orcid-profile"]
        id = profile_dict["orcid-identifier"]["path"]

        profile = TempOrcidProfile.query.get(id)


        created_timestamp = profile_dict["orcid-history"]["submission-date"]["value"]
        created = datetime.datetime.fromtimestamp(created_timestamp/1000).isoformat()
        modified_timestamp = profile_dict["orcid-history"]["last-modified-date"]["value"]
        modified = datetime.datetime.fromtimestamp(modified_timestamp/1000).isoformat()
        created_method = profile_dict["orcid-history"]["creation-method"]

        try:
            has_email = profile_dict["orcid-activities"]["verified-email"]["value"]
        except (KeyError, TypeError):
            has_email = None

        try:
            given_names = profile_dict["orcid-bio"]["personal-details"]["given-names"]["value"]
        except (TypeError,):
            given_names = None

        try:
            family_name = profile_dict["orcid-bio"]["personal-details"]["family-name"]["value"]
        except (TypeError,):
            family_name = None

        try:
            credit_name = profile_dict["orcid-bio"]["personal-details"]["credit-name"]["value"]
        except (TypeError,):
            credit_name = None

        try:
            works = profile_dict["orcid-activities"]["orcid-works"]["orcid-work"]
            if not works:
                works = []
        except TypeError:
            works = []

        # now go through and look at the works in more detail
        titles, dois, dois_since_2010 = [], [], []
        if works:
            # from http://kitchingroup.cheme.cmu.edu/blog/2015/03/28/The-orcid-api-and-generating-a-bibtex-file-from-it/

            for i, result in enumerate(works):

                try:
                    title = str(result['work-title']['title']['value'].encode('utf-8'))
                except TypeError:
                    title = ""
                doi = ""

                if result.get('work-external-identifiers', []):
                    for x in result.get('work-external-identifiers', []):
                        for eid in result['work-external-identifiers']['work-external-identifier']:
                            if eid['work-external-identifier-type'] == 'DOI':
                                doi = str(eid['work-external-identifier-id']['value'].encode('utf-8')).lower()

                # AIP journals tend to have a \n in the DOI, and the doi is the second line. we get
                # that here.
                if len(doi.split('\n')) == 2:
                    doi = doi.split('\n')[1]

                pub_date = result.get('publication-date', None)
                if pub_date:
                    year = pub_date.get('year', None).get('value').encode('utf-8')
                else:
                    year = 'Unknown'

                # Try to minimize duplicate entries that are found
                dup = False
                if (title and title.lower() in titles):
                    dup = True
                if (doi and doi in dois):
                    dup = True

                if not dup:
                    # truncate title to first 50 characters
                    print('| {3} | {0}  | {1} | [[doi:{2}]]|'.format(title[0:50], year, doi, result['work-type']))

                    if title:
                        titles.append(title.lower())
                    if doi:
                        dois.append(doi)
                        if year and year != 'Unknown' and int(year) > 2011:
                            dois_since_2010.append(doi)

                        data_to_add = dict(
                            doi=doi, 
                            year=year,
                            title=title
                            )
                        product = TempProduct(**data_to_add)
                        print "adding doi", doi, "to orcid", id
                        profile.products.append(product)


        # save to db
        print id, len(works), len(dois), len(dois_since_2010), created, modified, created_method, given_names, family_name

        # data_to_add = dict(
        #     id=id,
        #     given_names=given_names,
        #     family_name=family_name,
        #     created=created,
        #     modified=modified,
        #     created_method=created_method,
        #     num_works=len(works),
        #     num_all_dois=len(dois),
        #     num_dois_since_2010=len(dois_since_2010)

        #     # don't bother adding dois in right now, it slows it down
        #     # dois = dois
        #     )
        # profile = TempOrcidProfile(**data_to_add)
        # db.session.add(profile)

        if len(dois) > 0:
            profile = TempOrcidProfile.query.get(id)
            profile.api_raw = json.dumps(data_dict["orcid-profile"])

        print u"\n\nadded to db: {}".format(profile)
        num_profiles_to_commit += 1

        if num_profiles_to_commit > 100:
            print "\n\nCOMMITTING\n\n"
            db.session.commit()
            num_profiles_to_commit = 0 


        # need this so doesn't hog memory, see https://blogs.it.ox.ac.uk/inapickle/2011/06/20/high-memory-usage-when-using-pythons-tarfile-module/
        tar.members = []  

def elapsed(since, round_places=2):
    return round(time.time() - since, round_places)


if __name__ == '__main__':
    start_time = time.time()
    store_dois()
    print "Got data in {}sec".format(elapsed(start_time))
