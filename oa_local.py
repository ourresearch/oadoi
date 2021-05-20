#!/usr/bin/python
# -*- coding: utf-8 -*-

import csv
import gzip
import urllib.error
import urllib.parse
import urllib.request

import requests

from app import doaj_issns
from app import doaj_titles
from app import logger
from util import normalize_issn

# for things not in jdap.
# right now the url fragments and the doi fragments are the same
# make these so they match the dois whenever possible

# "10.1101/" is bioarxiv but don't include because is also other
# subscription journal prefixes

preprint_url_fragments = [
    "10.1038/npre.",
    "arxiv.org/",
    "10.15200/winn.",
    "/peerj.preprints",
    ".figshare.",
    "bioarxiv.org",
    "10.15363/" #thinklab
]
dataset_url_fragments = [
                 "/dryad.",
                 "/zenodo.",
                 ".gbif.org/"
                 ]
open_url_fragments = preprint_url_fragments + dataset_url_fragments

preprint_doi_fragments = preprint_url_fragments
dataset_doi_fragments = dataset_url_fragments
open_doi_fragments = preprint_doi_fragments + dataset_doi_fragments

open_journal_doi_prefixes = [
    '10.7554/elife.',
]


def closed_manuscript_license_urls():
    return [
        'https://www.intellectbooks.com/self-archiving#accepted-manuscript-during-embargo',
    ]

def is_oa_license(license_url):
    """
    This function returns whether we expect a publication under a given license
    to be freely available from the publisher.

    Licenses are as expressed in CrossRef: see https://api.crossref.org/licenses
    """
    # originally from dissemin: https://github.com/dissemin/dissemin/blob/0aa00972eb13a6a59e1bc04b303cdcab9189406a/backend/crossref.py#L97
    # thanks dissemin!
    # Licenses considered OA, as stored by CrossRef
    oa_licenses = {
        "http://koreanjpathol.org/authors/access.php",
        "http://olabout.wiley.com/WileyCDA/Section/id-815641.html",
        "http://pubs.acs.org/page/policy/authorchoice_ccby_termsofuse.html",
        "http://pubs.acs.org/page/policy/authorchoice_ccbyncnd_termsofuse.html",
        "http://pubs.acs.org/page/policy/authorchoice_termsofuse.html",
        "http://www.elsevier.com/open-access/userlicense/1.0/"
    }

    if "creativecommons.org/licenses/" in license_url:
        return True

    if license_url in oa_licenses:
        return True

    return False


def is_open_via_doaj(issns, all_journals, pub_year=None):
    if issns:
        return is_open_via_doaj_issn(issns, pub_year)
    else:
        return is_open_via_doaj_journal(all_journals, pub_year)

def is_open_via_doaj_issn(issns, pub_year=None):
    if issns:
        for issn in issns:
            issn_no_hypen = issn.replace("-", "")
            for (row_issn_no_hyphen, row_license, doaj_start_year) in doaj_issns:
                if issn_no_hypen == row_issn_no_hyphen:
                    if doaj_start_year and pub_year and (doaj_start_year > pub_year):
                        pass # journal wasn't open yet!
                    else:
                        # logger.info(u"open: doaj issn match!")
                        if row_license == "Publisher's own license":
                            return "publisher-specific license"

                        return find_normalized_license(row_license)
    return False

# returns true if is in open list of issns, or doaj issns
# example:  https://doi.org/10.14740/jh305w
# right now this doesn't include years journal goes OA, so causes errors
# for example, error for http://pubs.rsc.org/en/Content/ArticleLanding/2014/RA/C4RA04523H#!divAbstract
# add years, maybe by crowdsourcing?  maybe just the issns that have dois?
# def is_open_via_open_issn_list(issns, pub_year=None):
#     if issns:
#         for issn in issns:
#             issn = remove_punctuation(issn)
#             if issn in open_issns:
#                 return True
#     if is_open_via_doaj_issn(issns, pub_year):
#         return True
#     return False


def doaj_journal_name_substitutions():
    return {
        "Babel": "Babel : Littératures Plurielles",
    }


def doaj_titles_to_skip():
    return [
        "AMM",
    ]


def is_open_via_doaj_journal(all_journals, pub_year=None):
    if not all_journals:
        return False

    if isinstance(all_journals, str):
        all_journals = [all_journals]

    for journal_name in all_journals:
        if journal_name:
            journal_name_encoded = journal_name.encode('utf-8')
            # override journal names when what Crossref gives us back
            # doesn't match what DOAJ has
            journal_name = doaj_journal_name_substitutions().get(journal_name, journal_name)

            journals_to_skip = doaj_titles_to_skip()
            if journal_name not in journals_to_skip:
                for (row_journal_name, row_license, doaj_start_year) in doaj_titles:
                    if journal_name_encoded.strip().lower() == row_journal_name.strip().lower():
                        if doaj_start_year and pub_year and (doaj_start_year > pub_year):
                            pass # journal wasn't open yet!
                        else:
                            # logger.info(u"open: doaj journal name match! {}".format(journal_name))
                            if row_license == "Publisher's own license":
                                return "publisher-specific license"

                            return find_normalized_license(row_license)
    return False

def is_open_via_datacite_prefix(doi):
    if doi:
        if any(doi.startswith(prefix) for prefix in get_datacite_doi_prefixes()):
            # logger.info(u"open: datacite match")
            return True
    return False


def is_open_via_publisher(publisher):
    if not publisher:
        return False

    # is needed to deal with components, because they don't return journal names and
    # so can't be looked up in DOAJ
    # spelling and case should match what crossref returns
    open_publishers = {
        "plos": 'implied-oa',
        "hindawi": 'implied-oa',
        "scielo": 'implied-oa',
        "Universidade de São Paulo": 'cc-by-nc-sa',
        "Universidade de Sao Paulo": 'cc-by-nc-sa',
        "Orpheus Instituut": 'cc-by-nc-nd',
    }
    for (open_publisher_name, oa_license) in open_publishers.items():
        if open_publisher_name.lower() in publisher.lower():
            return oa_license

    return False


def is_open_via_publisher_genre(publisher, genre):
    open_publisher_genres = [
        ['Atlantis Press', 'proceedings-article', 'cc-by-nc'],
    ]

    for (open_publisher, open_genre, oa_license) in open_publisher_genres:
        if publisher and open_publisher.lower() in publisher.lower() and open_genre == genre:
            return oa_license

    return False


def is_open_via_manual_journal_setting(issns, pub_year=None):
    issns = issns or []

    #  Journal of Integrative Neuroscience
    if '0219-6352' in issns and pub_year >= 2018:
        return True

    #  Reviews in Cardiovascular Medicine
    if '1530-6550' in issns and pub_year >= 2018:
        return True

    # Bulletin of the American Mathematical Society
    if '0273-0979' in issns:
        return True

    # D-Lib Magazine
    if '1082-9873' in issns:
        return True

    # NeuroImage
    if '1053-8119' in issns and pub_year >= 2020:
        return True

    # European Psychiatry
    if '0924-9338' in issns and pub_year >= 2020:
        return True

    # The Breast
    if '0960-9776' in issns and pub_year >= 2020:
        return True

    # Journal of Applied Learning & Teaching
    if '2591-801X' in issns:
        return True

    # ACTA hydrotechnica
    if '0352-3551' in issns:
        return True

    return False


def manual_gold_journal_license(issn_l):
    licenses = {
        # ACTA hydrotechnica
        '0352-3551': 'cc-by-nc-sa'  # https://actahydrotechnica.fgg.uni-lj.si/en/
    }

    return licenses.get(issn_l, None)


_wrong_license_issns = set(map(normalize_issn, [
    '1348-8643',  # Oral science international
]))


def is_open_via_license_urls(licenses, issns):
    for issn in issns or []:
        if normalize_issn(issn) in _wrong_license_issns:
            return False

    for license in licenses:
        if is_oa_license(license['url']):
            # logger.info(u"open: licence!")
            return license
    return False


def is_open_via_doi_fragment(doi):
    if doi:
        if any(fragment in doi for fragment in open_doi_fragments):
            # logger.info(u"open: doi fragment!")
            return True
    return False


def is_open_via_journal_doi_prefix(doi):
    if doi:
        if any(doi.startswith(prefix) for prefix in open_journal_doi_prefixes):
            return True
    return False


def is_open_via_url_fragment(url):
    if url:
        if any(fragment in url for fragment in open_url_fragments):
            # logger.info(u"open: url fragment!")
            return True
    return False


def find_normalized_license(text):
    if not text:
        return None

    normalized_text = text.replace(" ", "").replace("-", "").lower()

    # the lookup order matters
    # assumes no spaces, no dashes, and all lowercase
    # inspired by https://github.com/CottageLabs/blackbox/blob/fc13e5855bd13137cf1ef8f5e93883234fdab464/service/licences.py
    # thanks CottageLabs!  :)

    license_lookups = [
        ("koreanjpathol.org/authors/access.php", "cc-by-nc"),  # their access page says it is all cc-by-nc now
        ("elsevier.com/openaccess/userlicense", "elsevier-specific: oa user license"),  #remove the - because is removed in normalized_text above
        ("pubs.acs.org/page/policy/authorchoice_termsofuse.html", "acs-specific: authorchoice/editors choice usage agreement"),

        ("creativecommons.org/licenses/byncnd", "cc-by-nc-nd"),
        ("creativecommonsattributionnoncommercialnoderiv", "cc-by-nc-nd"),
        ("ccbyncnd", "cc-by-nc-nd"),

        ("creativecommons.org/licenses/byncsa", "cc-by-nc-sa"),
        ("creativecommonsattributionnoncommercialsharealike", "cc-by-nc-sa"),
        ("ccbyncsa", "cc-by-nc-sa"),

        ("creativecommons.org/licenses/bynd", "cc-by-nd"),
        ("creativecommonsattributionnoderiv", "cc-by-nd"),
        ("ccbynd", "cc-by-nd"),

        ("creativecommons.org/licenses/bysa", "cc-by-sa"),
        ("creativecommonsattributionsharealike", "cc-by-sa"),
        ("ccbysa", "cc-by-sa"),

        ("creativecommons.org/licenses/bync", "cc-by-nc"),
        ("creativecommonsattributionnoncommercial", "cc-by-nc"),
        ("ccbync", "cc-by-nc"),

        ("creativecommons.org/licenses/by", "cc-by"),
        ("creativecommonsattribution", "cc-by"),
        ("ccby", "cc-by"),

        ("creativecommons.org/publicdomain/zero", "cc0"),
        ("creativecommonszero", "cc0"),

        ("creativecommons.org/publicdomain/mark", "pd"),
        ("publicdomain", "pd"),

        # ("openaccess", "oa")
    ]

    for (lookup, license) in license_lookups:
        if lookup in normalized_text:
            if license == "pd":
                try:
                    if "worksnotinthepublicdomain" in normalized_text:
                        return None
                except:
                    # some kind of unicode exception
                    return None
            return license
    return None


# truncate table pmcid_lookup

# python -c 'import oa_local; oa_local.save_pmcid_file();'
# REMEMBER WHEN DONE: CHECK THE RIGHT THINGS GOT PUT IN THE RIGHT COLUMNS
# psql `heroku config:get DATABASE_URL`?ssl=true -c "\copy pmcid_lookup (doi, pmcid, release_date) FROM 'data/extract_PMC-ids.csv' WITH CSV;"
# THEN CHECK THE RIGHT THINGS GOT PUT IN THE RIGHT COLUMNS

def save_pmcid_file():
    logger.info("starting ftp get")
    # fieldnames = "Journal Title,ISSN,eISSN,Year,Volume,Issue,Page,DOI,PMCID,PMID,Manuscript Id,Release Date".split(",")
    urllib.request.urlretrieve('ftp://ftp.ncbi.nlm.nih.gov/pub/pmc/PMC-ids.csv.gz', 'data/PMC-ids.csv.gz')
    logger.info("finished ftp get")
    csvfile = gzip.open('data/PMC-ids.csv.gz', 'rb')
    logger.info("finished unzip")
    my_reader = csv.DictReader(csvfile)

    outfile = open("data/extract_PMC-ids.csv", "w")  # write, deleting what is there

    for row in my_reader:
        # make sure it has a doi
        outfile.writelines("{},{},{}\n".format(row["DOI"], row["PMCID"].lower(), row["Release Date"]))
    outfile.close()  # open and write it every page, for safety
    csvfile.close()
    print("done")


# create table pmcid_published_version_lookup (pmcid text)
# create index pmcid_published_version_lookup_pmcid_idx on pmcid_published_version_lookup(pmcid)
# or
# truncate table pmcid_published_version_lookup
# heroku run bash
# python -c 'import oa_local; oa_local.save_pmcid_published_version_lookup();'
# psql `heroku config:get DATABASE_URL`?ssl=true -c "\copy pmcid_published_version_lookup FROM 'data/extract_PMC-published-manuscripts.csv' WITH CSV;"
def save_pmcid_published_version_lookup():
    retstart = 0
    pagesize = 100*1000  # the max retmax is 100k
    retmax = pagesize
    outfile = open("data/extract_PMC-published-manuscripts.csv", "w")  # write, deleting what is there

    while retmax >= pagesize:
        # look for published, because want to default to author manuscript if we don't know for sure it is published
        url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pmc&term=pmc%20all[filter]%20NOT%20author%20manuscript[filter]&retmax={retmax}&retstart={retstart}&retmode=json".format(
            retmax=retmax, retstart=retstart)

        r = requests.get(url)
        json_data = r.json()
        count = int(json_data["esearchresult"]["count"])
        logger.info("got page {} of {}".format(retstart/retmax, count/retmax))
        retmax = int(json_data["esearchresult"]["retmax"])  # get new retmax, which is 0 when no more pages left
        published_version_pmcids_raw = json_data["esearchresult"]["idlist"]
        published_version_pmcids = ["pmc{}".format(id) for id in published_version_pmcids_raw]
        print("got {} published_version_pmcids".format(len(published_version_pmcids)))
        for pmcid in published_version_pmcids:
            outfile.writelines("{}\n".format(pmcid))
        retstart += retmax
    outfile.close()  # open and write it every page, for safety
    print("done")


def get_datacite_doi_prefixes():
    datacite_doi_prefixes = ["{}/".format(prefix) for prefix in datacite_doi_prefixes_string.split("\n") if prefix]
    return datacite_doi_prefixes

# removed this one because paywalled.  see 10.1515/fabl.1988.29.1.21
# 10.1515

# removed this one because paywalled.  see https://doi.org/10.1513/AnnalsATS.201610-815OC
# 10.1513

# from http://stats.datacite.org/
datacite_doi_prefixes_string = """
10.1184
10.1285
10.1594
10.2195
10.2311
10.2312
10.2313
10.2314
10.239
10.3203
10.3204
10.3205
10.3206
10.3207
10.3249
10.3285
10.3334
10.3886
10.3929
10.3931
10.3932
10.3933
10.4118
10.4119
10.412
10.4121
10.4122
10.4123
10.4124
10.4125
10.4126
10.4224
10.4225
10.4226
10.4227
10.4228
10.4229
10.423
10.4231
10.4232
10.4233
10.4246
10.4429
10.506
10.5061
10.5062
10.5063
10.5064
10.5065
10.5066
10.5067
10.5068
10.5069
10.507
10.5071
10.5073
10.5075
10.5076
10.5078
10.5079
10.5156
10.5157
10.5159
10.516
10.5161
10.5162
10.5165
10.5166
10.5167
10.5169
10.517
10.5255
10.5256
10.5257
10.5258
10.5259
10.5277
10.5278
10.5279
10.528
10.5281
10.5282
10.5283
10.5284
10.5285
10.5286
10.5287
10.5288
10.529
10.5291
10.5438
10.5439
10.544
10.5441
10.5442
10.5443
10.5444
10.5445
10.5446
10.5447
10.5449
10.5451
10.5452
10.5517
10.5518
10.5519
10.552
10.5521
10.5522
10.5523
10.5524
10.5525
10.5526
10.5675
10.5676
10.5677
10.5678
10.568
10.5681
10.5682
10.5684
10.5878
10.5879
10.588
10.5881
10.5882
10.5883
10.5884
10.5885
10.5886
10.5887
10.5903
10.5904
10.5905
10.5907
10.5967
10.5968
10.6067
10.6068
10.6069
10.607
10.6071
10.6072
10.6073
10.6074
10.6075
10.6076
10.6077
10.6078
10.6079
10.608
10.6081
10.6082
10.6083
10.6084
10.6085
10.6086
10.6091
10.6092
10.6093
10.6094
10.6096
10.6098
10.6099
10.61
10.6101
10.6102
10.6103
10.6104
10.6105
10.7264
10.7265
10.7266
10.7267
10.7268
10.7269
10.727
10.7271
10.7272
10.7273
10.7274
10.7275
10.7276
10.7277
10.7278
10.7279
10.728
10.7281
10.7282
10.7283
10.7284
10.7285
10.7286
10.7287
10.7288
10.7289
10.729
10.7291
10.7292
10.7293
10.7294
10.7295
10.7296
10.7297
10.7298
10.7299
10.73
10.7301
10.7302
10.7303
10.734
10.7477
10.7478
10.748
10.7482
10.7483
10.7484
10.7485
10.7486
10.7487
10.7488
10.7489
10.749
10.7491
10.7794
10.7795
10.7796
10.7797
10.7799
10.78
10.7801
10.7802
10.7803
10.7804
10.7805
10.7806
10.7807
10.7808
10.789
10.7891
10.7892
10.7907
10.7908
10.7909
10.791
10.7911
10.7912
10.7913
10.7914
10.7915
10.7916
10.7917
10.7919
10.792
10.7921
10.7922
10.7923
10.7924
10.7925
10.7926
10.7927
10.7928
10.7929
10.793
10.7931
10.7932
10.7933
10.7934
10.7935
10.7936
10.7937
10.7938
10.7939
10.794
10.7942
10.7944
10.7945
10.7946
10.1157
10.11571
10.11574
10.11575
10.11577
10.11578
10.11581
10.11582
10.11584
10.11588
10.12682
10.12684
10.12685
10.12686
10.12751
10.12752
10.12753
10.12754
10.12757
10.12758
10.12759
10.1276
10.12761
10.12762
10.12763
10.12764
10.12765
10.12766
10.12767
10.1277
10.13009
10.1301
10.13011
10.13012
10.13013
10.13014
10.13016
10.13019
10.1302
10.13021
10.13022
10.13023
10.13025
10.13026
10.13027
10.13028
10.13091
10.13092
10.13093
10.13094
10.13095
10.13096
10.13098
10.13099
10.13116
10.13117
10.13125
10.13127
10.13128
10.1313
10.13131
10.13133
10.13135
10.13136
10.13137
10.13138
10.1314
10.13141
10.13142
10.13143
10.13146
10.13147
10.13148
10.13149
10.1315
10.13151
10.13152
10.13153
10.13154
10.13155
10.14272
10.14273
10.14274
10.14276
10.14277
10.14279
10.1428
10.14282
10.14283
10.14284
10.14285
10.14286
10.14287
10.14288
10.14289
10.14291
10.14454
10.14455
10.14456
10.14457
10.14458
10.14459
10.14462
10.14463
10.14464
10.14465
10.14466
10.14469
10.1447
10.14471
10.14473
10.14749
10.1475
10.14751
10.14753
10.14754
10.14755
10.14756
10.14758
10.14759
10.1476
10.14761
10.14763
10.14764
10.14765
10.14766
10.14767
10.1512
10.15121
10.15122
10.15123
10.15124
10.15125
10.15126
10.15127
10.15128
10.15129
10.15131
10.15132
10.15133
10.15134
10.15135
10.15136
10.15138
10.15139
10.15141
10.15142
10.15143
10.15144
10.15146
10.15147
10.15149
10.15152
10.15154
10.15155
10.15156
10.15157
10.1516
10.15161
10.15162
10.15163
10.15165
10.15167
10.15169
10.15454
10.15455
10.15457
10.15458
10.15461
10.15462
10.15463
10.15465
10.15466
10.15467
10.15468
10.15469
10.1547
10.15472
10.15473
10.15474
10.15475
10.15476
10.15477
10.15478
10.15479
10.1548
10.15482
10.15483
10.15484
10.15488
10.15489
10.1549
10.15491
10.15496
10.15497
10.15498
10.155
10.15501
10.15502
10.15503
10.1577
10.15771
10.15772
10.15773
10.15774
10.15775
10.15776
10.15778
10.15779
10.1578
10.15781
10.15783
10.15784
10.15785
10.15786
10.15787
10.15788
10.16904
10.16905
10.16908
10.16909
10.1691
10.17019
10.1702
10.17021
10.17026
10.17028
10.17029
10.1703
10.17031
10.17032
10.17033
10.17034
10.17035
10.17036
10.17037
10.17038
10.17039
10.17044
10.17045
10.17047
10.17048
10.17166
10.17167
10.17169
10.17171
10.17172
10.17173
10.17174
10.17175
10.17176
10.17177
10.17179
10.1718
10.17181
10.17182
10.17183
10.17185
10.17188
10.1719
10.17192
10.17193
10.17194
10.17195
10.17201
10.17202
10.17203
10.17204
10.17205
10.17591
10.17592
10.17593
10.17594
10.176
10.17601
10.17602
10.17603
10.17604
10.17605
10.17606
10.17608
10.17611
10.17612
10.17613
10.17614
10.17615
10.17616
10.17617
10.17619
10.17624
10.17625
10.17626
10.17627
10.17629
10.1763
10.17632
10.17633
10.17634
10.17635
10.17636
10.17638
10.17639
10.17861
10.17862
10.17864
10.17865
10.17866
10.17867
10.17869
10.17871
10.17874
10.17876
10.17877
10.17879
10.1788
10.17882
10.17885
10.17886
10.17888
10.1789
10.17891
10.17892
10.17893
10.17909
10.1791
10.17911
10.17912
10.17914
10.17917
10.17919
10.18112
10.18115
10.18116
10.18118
10.18121
10.18122
10.18126
10.1813
10.18131
10.18133
10.18134
10.18135
10.18138
10.18142
10.18143
10.18145
10.18146
10.18147
10.18148
10.1815
10.18151
10.18153
10.18154
10.18156
10.18157
10.18162
10.18163
10.18167
10.18169
10.1817
10.18171
10.18416
10.18417
10.18418
10.18419
10.18421
10.18422
10.18424
10.18429
10.1843
10.18431
10.18433
10.18434
10.18435
10.18437
10.18438
10.1844
10.18443
10.18453
10.18454
10.18455
10.18458
10.18459
10.18461
10.18463
10.18464
10.18725
10.18732
10.18737
10.18738
10.18739
10.1874
10.18747
10.18757
10.2035
10.20355
10.2036
10.20361
10.20362
10.20364
10.20376
10.20385
10.20386
10.20391
10.2122"""




#### HOW WE BUILD data/doaj_issns.json and data/doaj_journals.json

#
# def get_doaj_journal_titles(doaj_rows):
#     journal_titles = []
#     for row in doaj_rows:
#         for column_name in ['Journal title', 'Alternative title']:
#             journal_title = row[column_name]
#             license = row['Journal license']
#             start_year = int(row['First calendar year journal provided online Open Access content'])
#             logger.info(journal_title)
#             logger.info(start_year)
#             if journal_title:
#                   # exclude alternative titles that are unpopular but easily mixed up with popular toll-access journals
#                   if journal_title not in ["RNA"]:
#                       journal_titles.append((journal_title, license, start_year))
#     return journal_titles
#
# def get_doaj_issns(doaj_rows):
#     issns = []
#     for row in doaj_rows:
#         for issn_column_name in ['Journal ISSN (print version)', 'Journal EISSN (online version)']:
#             issn = row[issn_column_name]
#             license = row['Journal license']
#             start_year = int(row['First calendar year journal provided online Open Access content'])
#             if issn:
#                 issns.append((issn, license, start_year))
#     return issns
#
# import csv
# import json
#
# def read_csv_file(filename):
#     logger.info(filename)
#     with open(filename, "r") as csv_file:
#         my_reader = csv.DictReader(csv_file)
#         rows = [row for row in my_reader]
#     return rows
#
# doaj_rows = read_csv_file("data/doaj_20170520_2031_utf8.csv")
#
# doaj_issns = get_doaj_issns(doaj_rows)
# with open("data/doaj_issns.json", "w") as fh:
#     json.dump(doaj_issns, fh, indent=4)
#
#
# doaj_titles = get_doaj_journal_titles(doaj_rows)
# with open("data/doaj_titles.json", "w") as fh:
#     json.dump(doaj_titles, fh, indent=4)
