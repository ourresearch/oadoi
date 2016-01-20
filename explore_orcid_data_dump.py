import tarfile
import json
import datetime
import re

from models.orcid_profile import TempOrcidProfile
from app import db

db.create_all()
db.session.commit()

def analyze_main():

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
        profile = data_dict["orcid-profile"]
        id = profile["orcid-identifier"]["path"]
        created_timestamp = profile["orcid-history"]["submission-date"]["value"]
        created = datetime.datetime.fromtimestamp(created_timestamp/1000).isoformat()
        modified_timestamp = profile["orcid-history"]["last-modified-date"]["value"]
        modified = datetime.datetime.fromtimestamp(modified_timestamp/1000).isoformat()
        created_method = profile["orcid-history"]["creation-method"]

        try:
            has_email = profile["orcid-activities"]["verified-email"]["value"]
        except (KeyError, TypeError):
            has_email = None

        try:
            given_names = profile["orcid-bio"]["personal-details"]["given-names"]["value"]
        except (TypeError,):
            given_names = None

        try:
            family_name = profile["orcid-bio"]["personal-details"]["family-name"]["value"]
        except (TypeError,):
            family_name = None

        try:
            credit_name = profile["orcid-bio"]["personal-details"]["credit-name"]["value"]
        except (TypeError,):
            credit_name = None

        try:
            works = profile["orcid-activities"]["orcid-works"]["orcid-work"]
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

if __name__ == '__main__':
    analyze_main()