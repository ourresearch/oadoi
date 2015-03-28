import pubmed

def make_profile(name, pmids):
    # save the profile-about

    for pmid in pmids:
        # put it on the scopus queue
        # skipping this for now
        pass

    # get all the infos in one big pull from pubmed
    # this is blocking and can take lord knows how long
    medline_records = pubmed.get_medline_records(pmids)


    # save all the medline records, in one big save to redis


    for record in medline_records:
        # put it in the refset queue
        pass

    return medline_records