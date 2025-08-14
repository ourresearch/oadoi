# -*- coding: utf-8 -*-

from collections import defaultdict

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import func

from app import db
import oa_evidence
from util import normalize_doi


class OAManual(db.Model):
    __tablename__ = 'oa_manual'

    id = db.Column(db.Integer, primary_key=True)
    doi = db.Column(db.Text, unique=True)
    response_jsonb = db.Column(JSONB)


def get_override_dict(pub):
    overrides_dict = get_overrides_dict()
    db_overrides_dict = db.session.query(OAManual).filter(func.lower(OAManual.doi) == func.lower(pub.doi)).first()

    if pub.doi in overrides_dict:
        return overrides_dict[pub.doi]
    elif db_overrides_dict:
        return db_overrides_dict.response_jsonb
    elif pub.issn_l in ["0143-6244", "1477-0849"]:
        # Journal of Biological Chemistry
        # ticket 28190
        # doi.org links resolve to jbc.org through JS redirect on linkinghub.elsevier.com
        # which applies rate limits, but CrossRef metadata and PDF confirm CC BY
        # https://doi.org/10.1016/j.jbc.2020.100199
        jbc = {
            "license": "cc-by",
            "evidence": "open (via page says license)",
            "oa_date": "2021-01-01",
            "pdf_url": pub.doi_url,
            "version": "publishedVersion",
            "host_type_set": "publisher"
        }
        return jbc
    elif pub.issn_l == '0860-021X':
        # Biology of Sport.
        # ticket 995
        # doi.org links resolve to biolsport.com, which is now possibly malicious
        return {}
    elif pub.issn_l == '2149-2980' and pub.best_host == 'publisher':
        # Kosuyolu Heart Journal
        # in DOAJ but doi.org links don't work
        return {}
    elif pub.issn_l == '2079-5696':
        # ticket 22141
        # Gynecology, doi.org links don't resolve
        return {}
    elif pub.issn_l in ['1642-5758', '0209-1712'] and pub.year and pub.year < 2016 and pub.best_host == 'publisher':
        # ticket 22157
        # Anestezjologia Intensywna Terapia. publisher changed but didn't update old DOIs
        return {}
    elif pub.issn_l == '1582-9596' and pub.best_host == 'publisher':
        # ticket 22257
        # Environmental Engineering and Management Journal, doi.org URLs lead to abstracts
        return {}
    elif pub.id == '10.1042/cs20200184' and pub.best_oa_location and '(via crossref license)' in pub.best_oa_location.evidence:
        return {}
    elif pub.id and pub.id.startswith('10.18267/pr.2019.los.186.'):
        return {
            "metadata_url": "https://msed.vse.cz/msed_2019/sbornik/toc.html",
            "host_type_set": "publisher",
            "version": "publishedVersion",
        }
    elif pub.issn_l == '1012-0254':
        # gold journal, doi URLs are broken. ticket 22821
        return {
            'metadata_url': 'https://journals.co.za/doi/{}'.format(pub.id.upper()),
            'version': 'publishedVersion',
            'host_type_set': 'publisher',
            'evidence': 'oa journal (via observed oa rate)',
        }
    elif pub.doi and pub.doi.startswith('10.1002/9781119237211.'):
        return {}
    else:
        return None


# things to set here:
#       license, free_metadata_url, free_pdf_url
# free_fulltext_url is set automatically from free_metadata_url and free_pdf_url

def get_overrides_dict():
    override_dict = defaultdict(dict)

    # cindy wu example
    override_dict["10.1038/nature21360"] = {
        "pdf_url": "https://arxiv.org/pdf/1703.01424.pdf",
        "version": "submittedVersion",
        "host_type_set": "repository",
        "evidence": "oa repository (manual)"
    }

    # example from twitter
    override_dict["10.1021/acs.jproteome.5b00852"] = {
        "pdf_url": "http://pubs.acs.org/doi/pdfplus/10.1021/acs.jproteome.5b00852",
        "host_type_set": "publisher",
        "version": "publishedVersion"
    }

    # have the unpaywall example go straight to the PDF, not the metadata page
    override_dict["10.1098/rspa.1998.0160"] = {
        "pdf_url": "https://arxiv.org/pdf/quant-ph/9706064.pdf",
        "version": "submittedVersion"
    }

    # missed, not in BASE, from Maha Bali in email
    override_dict["10.1080/13562517.2014.867620"] = {
        "pdf_url": "http://dar.aucegypt.edu/bitstream/handle/10526/4363/Final%20Maha%20Bali%20TiHE-PoD-Empowering_Sept30-13.pdf",
        "version": "submittedVersion"
    }

    # otherwise links to figshare match that only has data, not the article
    override_dict["110.1126/science.aaf3777"] = {}

    #otherwise links to a metadata page that doesn't have the PDF because have to request a copy: https://openresearch-repository.anu.edu.au/handle/1885/103608
    override_dict["10.1126/science.aad2622"] = {
        "pdf_url": "https://lra.le.ac.uk/bitstream/2381/38048/6/Waters%20et%20al%20draft_post%20review_v2_clean%20copy.pdf",
        "version": "submittedVersion"
    }

    # otherwise led to http://www.researchonline.mq.edu.au/vital/access/services/Download/mq:39727/DS01 and authorization error
    override_dict["10.1126/science.aad2622"] = {}

    # else goes here: http://www.it-c.dk/people/schmidt/papers/complexity.pdf
    override_dict["10.1007/978-1-84800-068-1_9"] = {}

    # otherwise led to https://dea.lib.unideb.hu/dea/bitstream/handle/2437/200488/file_up_KMBT36220140226131332.pdf;jsessionid=FDA9F1A60ACA567330A8B945208E3CA4?sequence=1
    override_dict["10.1007/978-3-211-77280-5"] = {}

    # otherwise led to publisher page but isn't open
    override_dict["10.1016/j.renene.2015.04.017"] = {}

    # override old-style webpage
    override_dict["10.1210/jc.2016-2141"] = {
        "pdf_url": "https://academic.oup.com/jcem/article-lookup/doi/10.1210/jc.2016-2141",
        "host_type_set": "publisher",
        "version": "publishedVersion",
    }

    # not indexing this location yet, from @rickypo
    override_dict["10.1207/s15327957pspr0203_4"] = {
        "pdf_url": "http://www2.psych.ubc.ca/~schaller/528Readings/Kerr1998.pdf",
        "version": "submittedVersion"
    }

    # mentioned in world bank as good unpaywall example
    override_dict["10.3386/w23298"] = {
        "pdf_url": "https://economics.mit.edu/files/12774",
        "version": "submittedVersion"
    }

    # from email, has bad citesserx cached version
    override_dict["10.1007/bf02693740"] = {
        "pdf_url": "http://citeseerx.ist.psu.edu/viewdoc/download?doi=10.1.1.536.6939&rep=rep1&type=pdf",
        "version": "publishedVersion"
    }

    # from email, has bad citesserx cached version
    override_dict["10.1126/science.1150952"] = {
        "pdf_url": "http://citeseerx.ist.psu.edu/viewdoc/download?doi=10.1.1.168.3796&rep=rep1&type=pdf",
        "version": "submittedVersion",
        "host_type_set": "repository"
    }

    # from email, has bad citesserx cached version
    override_dict["10.1515/eqc.2007.295"] = {
        "pdf_url": "http://citeseerx.ist.psu.edu/viewdoc/download?doi=10.1.1.543.7752&rep=rep1&type=pdf",
        "version": "publishedVersion",
        "host_type_set": "repository"
    }

    # from email
    override_dict["10.1038/nature21377"] = {
        "pdf_url": "http://eprints.whiterose.ac.uk/112179/1/ppnature21377_Dodd_for%20Symplectic.pdf",
        "version": "submittedVersion"
    }

    # from email
    override_dict["10.1016/j.gtc.2016.09.007"] = {
        "pdf_url": "https://cora.ucc.ie/bitstream/handle/10468/3544/Quigley_Chapter.pdf?sequence=1&isAllowed=y",
        "version": "acceptedVersion"
    }

    # stephen hawking's thesis
    override_dict["10.17863/cam.11283"] = {
        "pdf_url": "https://www.repository.cam.ac.uk/bitstream/handle/1810/251038/PR-PHD-05437_CUDL2017-reduced.pdf?sequence=15&isAllowed=y",
        "version": "publishedVersion"
    }

    # from email
    override_dict["10.1152/advan.00040.2005"] = {
        "pdf_url": "https://www.physiology.org/doi/pdf/10.1152/advan.00040.2005",
        "version": "publishedVersion"
    }

    # from email
    override_dict["10.1016/j.chemosphere.2014.07.047"] = {
        "pdf_url": "https://manuscript.elsevier.com/S0045653514009102/pdf/S0045653514009102.pdf",
        "version": "submittedVersion"
    }

    # from email
    override_dict["10.4324/9780203900956"] = {}

    # from email
    override_dict["10.3810/psm.2010.04.1767"] = {
        "pdf_url": "http://cupola.gettysburg.edu/cgi/viewcontent.cgi?article=1014&context=healthfac",
        "version": "publishedVersion"
    }

    # from email
    override_dict["10.1016/S0140-6736(17)33308-1"] = {
        "pdf_url": "https://www.rug.nl/research/portal/files/64097453/Author_s_version_Gonadotrophins_versus_clomiphene_citrate_with_or_without_intrauterine_insemination_in_women.pdf",
        "version": "acceptedVersion",
        "host_type_set": "repository"
    }

    # from email
    override_dict["10.1093/joclec/nhy009"] = {
        "pdf_url": "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3126848",
        "host_type_set": "repository"
    }

    # from email
    override_dict["10.1038/s41477-017-0019-3"] = {
        "pdf_url": "https://www.repository.cam.ac.uk/bitstream/handle/1810/270235/3383_1_merged_1502805167.pdf?sequence=1&isAllowed=y",
        "version": "acceptedVersion",
        "host_type_set": "repository"
    }

    # from email
    override_dict["10.1029/wr015i006p01633"] = {
        "pdf_url": "http://citeseerx.ist.psu.edu/viewdoc/download?doi=10.1.1.475.497&rep=rep1&type=pdf",
        "version": "publishedVersion"
    }

    # from email, zenodo
    override_dict["10.1080/01650521.2018.1460931"] = {
        "metadata_url": "https://zenodo.org/record/1236622",
        "host_type_set": "repository",
        "version": "acceptedVersion"
    }

    # from email
    override_dict["10.3928/01477447-20150804-53"] = {}

    # from twitter
    override_dict["10.1103/physreva.97.013421"] = {
        "pdf_url": "https://arxiv.org/pdf/1711.10074.pdf",
        "version": "submittedVersion"
    }

    # from email
    override_dict["10.1016/j.amjmed.2005.09.031"] = {
        "pdf_url": "https://www.amjmed.com/article/S0002-9343(05)00885-5/pdf",
        "version": "publishedVersion"
    }

    # from email
    override_dict["10.1080/15348458.2017.1327816"] = {}

    # from chorus
    override_dict["10.1103/physrevd.94.052011"] = {
        "pdf_url": "https://link.aps.org/accepted/10.1103/PhysRevD.94.052011",
        "version": "acceptedVersion",
    }
    override_dict["10.1063/1.4962501"] = {
        "pdf_url": "https://aip.scitation.org/doi/am-pdf/10.1063/1.4962501",
        "version": "acceptedVersion",
        "host_type_set": "repository"
    }

    # from email, broken citeseer link
    override_dict["10.2202/1949-6605.1908"] = {
        "pdf_url": "http://citeseerx.ist.psu.edu/viewdoc/download?doi=10.1.1.535.9289&rep=rep1&type=pdf",
        "version": "publishedVersion"
    }

    # from email
    override_dict["10.1561/1500000012"] = {
        "pdf_url": "http://citeseerx.ist.psu.edu/viewdoc/download?doi=10.1.1.174.8814&rep=rep1&type=pdf",
        "version": "publishedVersion"
    }

    # from email
    override_dict["10.1137/s0036142902418680"] = {
        "pdf_url": "http://citeseerx.ist.psu.edu/viewdoc/download?doi=10.1.1.144.7627&rep=rep1&type=pdf",
        "version": "publishedVersion"
    }

    # from email
    override_dict["10.1088/1741-2552/aab4e4"] = {
        "pdf_url": "http://iopscience.iop.org/article/10.1088/1741-2552/aab4e4/pdf",
        "version": "publishedVersion"
    }

    # from email
    override_dict["10.1145/1031607.1031615"] = {
        "pdf_url": "http://citeseerx.ist.psu.edu/viewdoc/download?doi=10.1.1.540.8125&rep=rep1&type=pdf",
        "version": "publishedVersion"
    }

    # from email
    override_dict["10.1007/s11227-016-1779-7"] = {
        "pdf_url": "https://hcl.ucd.ie/system/files/TJS-Hasanov-2016.pdf",
        "version": "publishedVersion",
        "host_type_set": "repository"
    }

    # from email
    override_dict["10.1016/s0020-0190(03)00351-x"] = {
        "pdf_url": "https://kam.mff.cuni.cz/~kolman/papers/noteb.ps",
        "version": "submittedVersion",
        "host_type_set": "repository"
    }

    # from email
    override_dict["10.1002/14651858.cd001704.pub4"] = {
        "pdf_url": "https://core.ac.uk/download/pdf/9440822.pdf",
        "version": "submittedVersion",
        "host_type_set": "repository"
    }

    # from email
    override_dict["10.1016/j.tetlet.2015.04.131"] = {
        "pdf_url": "https://www.sciencedirect.com/sdfe/pdf/download/read/aam/noindex/pii/S0040403915007881",
        "version": "acceptedVersion",
        "host_type_set": "publisher"
    }

    # from email
    override_dict["10.1016/j.nima.2016.04.104"] = {
        "pdf_url": "http://cds.cern.ch/record/2239750/files/1-s2.0-S0168900216303400-main.pdf",
        "version": "publishedVersion",
        "host_type_set": "repository"
    }

    # from email
    override_dict["10.1056/NEJM199406233302502"] = {
        "pdf_url": "https://www.nejm.org/doi/full/10.1056/NEJM199406233302502",
        "version": "publishedVersion",
        "host_type_set": "publisher"
    }

    # from email
    override_dict["10.1056/NEJMra1201534"] = {
        "pdf_url": "https://www.nejm.org/doi/pdf/10.1056/NEJMra1201534",
        "version": "publishedVersion",
        "host_type_set": "publisher"
    }

    # from email
    override_dict["10.1016/j.cmet.2018.03.012"] = {
        "pdf_url": "https://www.biorxiv.org/content/biorxiv/early/2018/01/15/245332.full.pdf",
        "version": "submittedVersion",
        "host_type_set": "repository"
    }

    # from email
    override_dict["10.1093/sf/65.1.1"] = {
        "pdf_url": "https://faculty.washington.edu/charles/new%20PUBS/A52.pdf",
        "version": "publishedVersion",
        "host_type_set": "repository"
    }

    # from email
    override_dict["10.1088/1751-8121/aabd9c"] = {}

    # from email
    override_dict["10.1017/CBO9781139173728.002"] = {}

    # from email
    override_dict["10.2174/97816810846711170101"] = {}

    # from email
    override_dict["10.1177/1354066196002003001"] = {}

    # from email
    override_dict["10.1093/bioinformatics/bty721"] = {}

    # from email
    override_dict["10.1088/1361-6528/aac7a4"] = {}

    # from email
    override_dict["10.1088/1361-6528/aac645"] = {}

    # from email
    override_dict["10.1111/1748-8583.12159"] = {}

    # from email
    override_dict["10.1042/BJ20080963"] = {}

    # from email
    override_dict["10.1136/bmj.j5007"] = {}

    # from email
    override_dict["10.1016/j.phrs.2017.12.007"] = {}

    # from email
    override_dict["10.4324/9781315770185"] = {}

    # from email
    override_dict["10.1108/PIJPSM-02-2016-0019"] = {}

    # from email
    override_dict["10.1016/j.ejca.2017.07.015"] = {}

    # from email
    override_dict["10.1080/14655187.2017.1469322"] = {}

    # from email
    override_dict["10.1080/02684527.2017.1407549"] = {}

    # from email
    override_dict["10.1093/jat/bky025"] = {}

    # from email
    override_dict["10.1016/j.midw.2009.07.004"] = {}

    # from email
    override_dict["10.1177/247553031521a00105"] = {}

    # from email
    override_dict["10.1002/0471445428"] = {}

    # from email
    override_dict["10.1007/978-3-642-31232-8"] = {}

    # ticket 267
    override_dict["10.1016/j.anucene.2014.08.021"] = {}

    # ticket 199
    # pdf has embedded password protection
    override_dict["10.22381/rcp1720184"] = {}

    # ticket 574
    # pdf has embedded password protection
    override_dict["10.22381/EMFM14220195"] = {}

    # ticket 256
    # journal in doaj but article not available
    override_dict["10.1016/j.mattod.2018.03.001"] = {}

    # ticket 277
    # pmh record with spurious title: oai:works.swarthmore.edu:fac-psychology-1039
    override_dict["10.1016/j.actpsy.2010.01.009"] = {}

    # ticket 280
    # green scrape gets overexcited about a .doc link
    override_dict["10.1108/09596111211217932"] = {}

    # ticket 279
    # match to wrong pdf, currently suppressed incorrectly by bad pdf check
    override_dict["10.1238/physica.topical.102a00059"] = {}

    # ticket 275
    override_dict["10.1039/c7nj03253f"] = {}

    # email
    override_dict['10.1007/978-3-642-30350-0'] = {}

    # ticket 135
    # bad title / last author match
    override_dict["10.1016/s0140-6736(17)31287-4"] = {}

    # ticket 98
    # two similar articles with this title
    override_dict["10.1002/14651858.CD012414.pub2"] = {}

    # ticket 322
    # pmh match on a cover sheet
    override_dict["10.1116/1.5046531"] = {}

    # ticket 631
    # withdrawn article
    override_dict["10.5812/jjm.3664"] = {}

    # ticket 832
    override_dict["10.5935/scd1984-8773.20168409"] = {}

    # ticket 1047
    # book chapter has a bronze tag
    override_dict["10.1002/9781119473992"] = {}

    # from email
    override_dict["10.1016/S0022-1996(00)00093-3"] = {
        "pdf_url": "http://citeseerx.ist.psu.edu/viewdoc/download?doi=10.1.1.475.3874&rep=rep1&type=pdf",
        "version": "submittedVersion",
        "host_type_set": "repository"
    }

    # from email
    override_dict["10.1177/088840649401700203"] = {
        "pdf_url": "http://citeseerx.ist.psu.edu/viewdoc/download?doi=10.1.1.1014.8577&rep=rep1&type=pdf",
        "version": "publishedVersion",
        "host_type_set": "repository"
    }

    # from email
    override_dict["10.7326/L18-0139"] = {
        "pdf_url": "http://annals.org/data/journals/aim/936928/aime201804170-l180139.pdf",
        "version": "publishedVersion",
        "host_type_set": "publisher"
    }

    # from email
    override_dict["10.1007/978-3-319-48881-3_55"] = {
        "pdf_url": "http://liu.diva-portal.org/smash/get/diva2:1063949/FULLTEXT01.pdf",
        "version": "acceptedVersion",
        "host_type_set": "repository"
    }

    # from email
    override_dict["10.1109/ICCVW.2015.86"] = {
        "pdf_url": "http://liu.diva-portal.org/smash/get/diva2:917646/FULLTEXT01",
        "version": "acceptedVersion",
        "host_type_set": "repository"
    }

    # from email
    override_dict["10.1109/tpds.2012.97"] = {
        "pdf_url": "https://www.cnsr.ictas.vt.edu/publication/06171175.pdf",
        "version": "publishedVersion",
        "host_type_set": "repository"
    }

    # ticket 261
    # crossref metadata points to wrong article
    override_dict["10.4149/BLL_2013_058"] = {
        "pdf_url": "http://www.elis.sk/download_file.php?product_id=3759&session_id=lnkeo437s8hv5t0r28g6ku93b0",
        "version": "publishedVersion",
        "host_type_set": "publisher"
    }

    # ticket 317
    # broken link on citeseer
    override_dict["10.1016/b978-1-55860-307-3.50012-5"] = {
        "pdf_url": "http://citeseerx.ist.psu.edu/viewdoc/download?doi=10.1.1.57.3196&rep=rep1&type=pdf",
        "version": "submittedVersion",
        "host_type_set": "repository"
    }

    # ticket 195
    # wrong registered landing page
    override_dict["10.21285/2227-2925-2018-8-2-9-18"] = {
        "metadata_url": "http://journals.istu.edu/izvestia_biochemi/journals/2018/02/articles/01",
        "version": "publishedVersion",
        "host_type_set": "publisher",
        "evidence": oa_evidence.oa_journal_doaj
    }

    # ticket 213
    # journal issue is open
    override_dict["10.14195/2182-7982_32"] = {
        "metadata_url": "https://doi.org/10.14195/2182-7982_32",
        "version": "publishedVersion",
        "host_type_set": "publisher"
    }

    override_dict["10.1016/S2213-8587(16)30320-5"] = {
        "pdf_url": "http://www.spdm.org.pt/media/1373/pku-guidelines_2017.pdf",
        "version": "publishedVersion",
        "host_type_set": "repository"
    }

    # ticket 433
    override_dict["10.1144/GSL.JGS.1846.002.01-02.54"] = {
        "metadata_url": "https://www.biodiversitylibrary.org/item/109652#page/473/mode/1up",
        "version": "publishedVersion",
        "host_type_set": "repository"
    }

    # ticket 223
    # pme record has wrong page url
    override_dict["10.1002/abc.207"] = {
        "pdf_url": "https://repository.library.northeastern.edu/files/neu:344561/fulltext.pdf",
        "metadata_url": "https://repository.library.northeastern.edu/files/neu:344561",
        "version": "submittedVersion",
        "host_type_set": "repository"
    }

    # ticket 304
    # inline citation pdf links
    override_dict["10.7766/alluvium.v3.1.05"] = {
        "metadata_url": "https://doi.org/10.7766/alluvium.v3.1.05",
        "version": "publishedVersion",
        "host_type_set": "publisher"
    }

    # ticket 376
    override_dict["10.1080/01639374.2017.1358232"] = {
        "pdf_url": "https://groups.niso.org/apps/group_public/download.php/17446/Understanding%20Metadata.pdf",
        "version": "publishedVersion",
        "host_type_set": "repository"
    }

    # ticket 539
    # malformed url in pmh record
    override_dict["10.1642/0004-8038(2007)124[1121:EOWNVT]2.0.CO;2"] = {
        "pdf_url": "https://repository.si.edu/bitstream/handle/10088/35181/NZP_Marra_2007-ECOLOGY_OF_WEST_NILE_VIRUS_TRANSMISSION_AND_ITS_IMPACT_ON_BIRDS_IN_THE_WESTERN_HEMISPHERE.pdf",
        "version": "publishedVersion",
        "host_type_set": "repository"
    }

    # https://github.com/Impactstory/unpaywall/issues/41
    # link to preprint with different DOI
    override_dict["10.1038/s41592-018-0235-4"] = {
        "metadata_url": "https://www.biorxiv.org/content/10.1101/306951v3",
        "pdf_url": "https://www.biorxiv.org/content/biorxiv/early/2018/07/24/306951.full.pdf",
        "version": "submittedVersion",
        "host_type_set": "repository"
    }

    # issue 530
    # unrelated pmh record has wrong DOI
    override_dict["10.1056/nejmoa063842"] = {
        "metadata_url": "https://www.nejm.org/doi/10.1056/NEJMoa063842",
        "version": "publishedVersion",
        "host_type_set": "publisher"
    }

    # issue 571
    # scrape finds supplementary file
    override_dict["10.21203/rs.2.11958/v1"] = {
        "metadata_url": "https://doi.org/10.21203/rs.2.11958/v1",
        "version": "submittedVersion",
        "host_type_set": "repository",
        "license": "cc-by"
    }

    # twitter
    override_dict['10.1002/jclp.22680'] = {
        'pdf_url': 'https://dl.uswr.ac.ir/bitstream/Hannan/62873/1/2018%20JCpsychology%20Volume%2074%20Issue%2011%20November%20%2811%29.pdf',
        'version': 'publishedVersion',
        'host_type_set': 'repository',
    }

    # ticket 680
    override_dict['10.17059/2015-4-27'] = {
        'metadata_url': 'http://economyofregion.com/archive/2015/57/2731/',
        'pdf_url': 'http://economyofregion.com/archive/2015/57/2731/pdf/',
        'version': 'publishedVersion',
        'host_type_set': 'publisher',
    }

    # ticket 681
    override_dict['10.17059/2016-1-19'] = {
        'metadata_url': 'http://economyofregion.com/archive/2016/58/2778/',
        'pdf_url': 'http://economyofregion.com/archive/2016/58/2778/pdf/',
        'version': 'publishedVersion',
        'host_type_set': 'publisher',
    }

    # ticket 743
    override_dict['10.1016/S0140-6736(07)61162-3'] = {
        'metadata_url': 'https://www.semanticscholar.org/paper/Cannabis-use-and-risk-of-psychotic-or-aff-ective-a-Moore-Zammit/6e5bc8bf7814c62db319632ca939ad68a6770d1b',
        'pdf_url': 'https://pdfs.semanticscholar.org/641e/6aba769421d4308d1ad107684eeca7f687d1.pdf',
        'version': 'publishedVersion',
        'host_type_set': 'repository',
    }

    # ticket 835
    override_dict['10.23912/9781911396512-3454'] = {
        'metadata_url': 'https://doi.org/10.23912/9781911396512-3454',
        'pdf_url': 'https://www.goodfellowpublishers.com/academic-publishing.php?promoCode=&partnerID=&housekeeping=getfile&productID=3657',
        'version': 'publishedVersion',
        'host_type_set': 'publisher',
    }

    # ticket 899, missing from IR
    override_dict['10.1080/0361526x.2019.1551004'] = {
        'metadata_url': 'https://inspire.redlands.edu/oh_articles/249/',
        'pdf_url': 'https://inspire.redlands.edu/cgi/viewcontent.cgi?article=1190&context=oh_articles',
        'version': 'publishedVersion',
        'host_type_set': 'repository',
        'license': 'cc-by-nc',
    }

    # ticket 1029, can't detect PDF
    override_dict['10.1891/2156-5287.8.4.252'] = {
        'metadata_url': 'https://doi.org/10.1891/2156-5287.8.4.252',
        'pdf_url': 'https://connect.springerpub.com/content/sgrijc/8/4/252.full.pdf',
        'version': 'publishedVersion',
        'host_type_set': 'publisher',
    }

    # ticket 1057, full issue pdf found first but has errors
    override_dict['10.5152/turkjnephrol.2020.3579'] = {
        'metadata_url': 'https://doi.org/10.5152/turkjnephrol.2020.3579',
        'pdf_url': 'https://turkjnephrol.org/Content/files/sayilar/420/84-88(2).pdf',
        'version': 'publishedVersion',
        'host_type_set': 'publisher',
    }

    # ticket 1064, doi.org/10.1016/j.jcmg.2012.07.005 redirects to 10.1016/j.jcmg.2012.08.001
    override_dict['10.1016/j.jcmg.2012.07.005'] = {
        'metadata_url': 'https://www.sciencedirect.com/science/article/pii/S1936878X12005748',
        'version': 'publishedVersion',
        'host_type_set': 'publisher',
    }

    # ticket 1084 faculty page
    override_dict['10.1016/j.jebo.2012.09.021'] = {
        'pdf_url': 'https://cpb-us-w2.wpmucdn.com/sites.wustl.edu/dist/c/2014/files/2019/06/tennis.pdf',
        'version': 'submittedVersion',
        'host_type_set': 'repository',
    }

    # ticket 1118, can't read landing page
    override_dict['10.3917/zil.006.0009'] = {
        'metadata_url': 'https://doi.org/10.3917/zil.006.0009',
        'version': 'publishedVersion',
        'host_type_set': 'publisher',
    }

    # ticket 1151, doi.org url 404
    override_dict['10.1001/jamafacial.2013.406'] = {
        'metadata_url': 'https://www.liebertpub.com/doi/10.1001/archfaci.2013.406',
        'version': 'publishedVersion',
        'host_type_set': 'publisher',
    }

    #ticket 1152, doi.org url leads to wrong article
    override_dict['10.1016/j.aott.2018.06.004'] = {
        'metadata_url': 'https://www.aott.org.tr/en/comparison-of-ultrasound-and-extracorporeal-shock-wave-therapy-in-lateral-epicondylosis-133459',
        'version': 'publishedVersion',
        'host_type_set': 'publisher',
        'evidence': 'oa journal (via doaj)',
        'license': 'cc-by-nc-nd',
    }

    #ticket 1162, can't download PDF
    override_dict['10.3406/ahess.1976.293748'] = {
        'metadata_url': 'https://www.persee.fr/doc/ahess_0395-2649_1976_num_31_4_293748',
        'version': 'publishedVersion',
        'host_type_set': 'repository',
        'license': 'cc-by-nc-sa',
    }

    #ticket 1184, missing from philarchive
    override_dict['10.1007/s10670-020-00241-4'] = {
        'metadata_url': 'https://philarchive.org/rec/LOGIAI',
        'pdf_url': 'https://philarchive.org/archive/LOGIAI',
        'version': 'acceptedVersion',
        'host_type_set': 'repository',
    }

    override_dict['10.1007/s11098-019-01378-x'] = {
        'metadata_url': 'https://philarchive.org/rec/LOGTST',
        'pdf_url': 'https://philarchive.org/archive/LOGTST',
        'version': 'acceptedVersion',
        'host_type_set': 'repository',
    }

    override_dict['10.1002/tht3.395'] = {
        'metadata_url': 'https://philarchive.org/rec/LOGSUR',
        'pdf_url': 'https://philarchive.org/archive/LOGSUR',
        'version': 'publishedVersion',
        'host_type_set': 'repository',
    }

    override_dict['10.3917/lig.764.0006'] = {
        'metadata_url': 'https://doi.org/10.3917/lig.764.0006',
        'version': 'publishedVersion',
        'host_type_set': 'publisher',
    }

    # ticket 1260, wrong doi url
    override_dict['10.5603/ait.a2017.0053'] = {
        'metadata_url': 'https://www.termedia.pl/Pharmacokinetic-drug-drug-interactions-in-the-intensive-care-unit-single-centre-experience-and-literature-review,118,38092,1,1.html',
        'version': 'publishedVersion',
        'host_type_set': 'publisher',
        'evidence': 'oa journal (via doaj)',
    }

    # ticket 22157, wrong doi url
    override_dict['10.5603/ait.a2015.0073'] = {
        'metadata_url': 'https://www.termedia.pl/Hemodynamic-monitoring-To-calibrate-or-not-to-calibrate-r-nPart-1-Calibrated-techniques,118,38312,0,1.html',
        'pdf_url': 'https://www.termedia.pl/Journal/-118/pdf-38312-10?filename=pages_487-500_article_43713.pdf',
        'version': 'publishedVersion',
        'host_type_set': 'publisher',
        'evidence': 'oa journal (via doaj)',
    }

    # ticket 22157, wrong doi url
    override_dict['10.5603/ait.a2015.0076'] = {
        'metadata_url': 'https://www.termedia.pl/Hemodynamic-monitoring-To-calibrate-or-not-to-calibrate-r-nPart-2-Non-calibrated-techniques,118,38313,0,1.html',
        'pdf_url': 'https://www.termedia.pl/Journal/-118/pdf-38313-10?filename=pages_501-516_article_43754.pdf',
        'version': 'publishedVersion',
        'host_type_set': 'publisher',
        'evidence': 'oa journal (via doaj)',
    }

    # ticket 3417, wrong doi url
    override_dict['10.15414/jmbfs.2016.5.special1.64-68'] = {
        'metadata_url': 'https://www.jmbfs.org/issue/february-2016-vol-5-special-1/jmbfs-2016_020-ivanuska/?issue_id=4120&article_id=18',
        'version': 'publishedVersion',
        'host_type_set': 'publisher',
        'evidence': 'oa journal (via doaj)',
    }

    # ticket 4625, wrong doi url
    override_dict['10.4103/1011-4564.204985'] = {
        'metadata_url': 'http://www.jmedscindmc.com/article.asp?issn=1011-4564;year=2017;volume=37;issue=2;spage=37;epage=43;aulast=Huang;type=0',
        'version': 'publishedVersion',
        'host_type_set': 'publisher',
        'evidence': 'oa journal (via doaj)',
    }

    override_dict['10.4103/jmedsci.jmedsci_99_16'] = {
        'metadata_url': 'http://www.jmedscindmc.com/article.asp?issn=1011-4564;year=2017;volume=37;issue=2;spage=44;epage=49;aulast=Doka;type=0',
        'version': 'publishedVersion',
        'host_type_set': 'publisher',
        'evidence': 'oa journal (via doaj)',
    }

    override_dict['10.4103/jmedsci.jmedsci_95_16'] = {
        'metadata_url': 'http://www.jmedscindmc.com/article.asp?issn=1011-4564;year=2017;volume=37;issue=2;spage=50;epage=55;aulast=Hsu;type=0',
        'version': 'publishedVersion',
        'host_type_set': 'publisher',
        'evidence': 'oa journal (via doaj)',
    }

    override_dict['10.4103/jmedsci.jmedsci_104_16'] = {
        'metadata_url': 'http://www.jmedscindmc.com/article.asp?issn=1011-4564;year=2017;volume=37;issue=2;spage=56;epage=60;aulast=Lin;type=0',
        'version': 'publishedVersion',
        'host_type_set': 'publisher',
        'evidence': 'oa journal (via doaj)',
    }

    override_dict['10.4103/jmedsci.jmedsci_100_16'] = {
        'metadata_url': 'http://www.jmedscindmc.com/article.asp?issn=1011-4564;year=2017;volume=37;issue=2;spage=61;epage=68;aulast=Shen;type=0',
        'version': 'publishedVersion',
        'host_type_set': 'publisher',
        'evidence': 'oa journal (via doaj)',
    }

    override_dict['10.4103/jmedsci.jmedsci_12_16'] = {
        'metadata_url': 'http://www.jmedscindmc.com/article.asp?issn=1011-4564;year=2017;volume=37;issue=2;spage=69;epage=71;aulast=Chaitra;type=0',
        'version': 'publishedVersion',
        'host_type_set': 'publisher',
        'evidence': 'oa journal (via doaj)',
    }

    override_dict['10.4103/jmedsci.jmedsci_92_15'] = {
        'metadata_url': 'http://www.jmedscindmc.com/article.asp?issn=1011-4564;year=2017;volume=37;issue=2;spage=72;epage=75;aulast=Huang;type=0',
        'version': 'publishedVersion',
        'host_type_set': 'publisher',
        'evidence': 'oa journal (via doaj)',
    }

    override_dict['10.4103/jmedsci.jmedsci_27_16'] = {
        'metadata_url': 'http://www.jmedscindmc.com/article.asp?issn=1011-4564;year=2017;volume=37;issue=2;spage=76;epage=79;aulast=Saha;type=0',
        'version': 'publishedVersion',
        'host_type_set': 'publisher',
        'evidence': 'oa journal (via doaj)',
    }

    # end ticket 4625

    # ticket 22137, doi url redirects to http, then https redirect fails
    override_dict['10.18845/te.v1i2.868'] = {
        'metadata_url': 'https://revistas.tec.ac.cr/index.php/tec_empresarial/article/view/868',
        'pdf_url': 'https://revistas.tec.ac.cr/index.php/tec_empresarial/article/view/868',
        'version': 'publishedVersion',
        'host_type_set': 'publisher',
        'evidence': 'oa journal (via doaj)',
    }

    # ticket 22208. 404 at doi url
    override_dict['10.26442/terarkh201890417-20'] = {
        "host_type_set": "publisher",
        "version": "publishedVersion",
        "evidence": "oa journal (via doaj)",
        "metadata_url": "https://ter-arkhiv.ru/0040-3660/article/view/32440",
        "license": "cc-by",
    }

    # ticket 22274. gold journal but DOI doesn't resolve
    override_dict['10.25251/skin.3.6.4'] = {
        'metadata_url': 'https://jofskin.org/index.php/skin/article/view/625',
        'version': 'publishedVersion',
        'host_type_set': 'publisher',
        'evidence': 'oa journal (via observed oa rate)',
    }

    # ticket 22287. journal in DOAJ, but article missing from https://sophia.ups.edu.ec/index.php/sophia/issue/view/151
    override_dict['10.17163/soph.n25.2018.03'] = {
        'metadata_url': 'https://www.redalyc.org/jatsRepo/4418/441855948003/html/index.html',
        'license': 'cc-by-nc-sa',
        'version': 'publishedVersion',
        'host_type_set': 'publisher',
        'evidence': 'oa journal (via doaj)',
    }

    # ticket 22562. journal in DOAJ, doi.org url 404s
    override_dict['10.1162/itid.2003.1.1.75'] = {
        'metadata_url': 'https://itidjournal.org/index.php/itid/article/view/136.html',
        'pdf_url': 'https://itidjournal.org/index.php/itid/article/download/136/136-472-1-PB.pdf',
        'license': 'cc-by-nc-sa',
        'version': 'publishedVersion',
        'host_type_set': 'publisher',
        'evidence': 'oa journal (via doaj)',
    }

    # ticket 22936. journal in DOAJ, doi.org url 404s, same article as above
    override_dict['10.1162/154475203771799720'] = {
        'metadata_url': 'https://itidjournal.org/index.php/itid/article/view/136.html',
        'pdf_url': 'https://itidjournal.org/index.php/itid/article/download/136/136-472-1-PB.pdf',
        'license': 'cc-by-nc-sa',
        'version': 'publishedVersion',
        'host_type_set': 'publisher',
        'evidence': 'oa journal (via doaj)',
    }

    # ticket 22674. doesn't want to link to PDF for some reason.
    override_dict['10.1101/2020.02.24.962878'] = {
        'metadata_url': 'https://doi.org/10.1101/2020.02.24.962878',
        'version': 'submittedVersion',
        'host_type_set': 'repository',
        'evidence': 'oa repository (via free pdf)',
    }

    # ticket 22562. journal in DOAJ, broken doi.org url
    override_dict['10.5505/tbdhd.2018.50251'] = {
        'metadata_url': 'http://dergi.bdhd.org.tr/eng/jvi.aspx?un=TBDHD-50251&volume=24&issue=2',
        'pdf_url': 'https://jag.journalagent.com/tbdhd/pdfs/TBDHD-50251-CASE_REPORT-YEKTAS.pdf',
        'license': 'cc-by-nc-nd',
        'version': 'publishedVersion',
        'host_type_set': 'publisher',
        'evidence': 'oa journal (via doaj)',
    }

    # ticket 22877. journal was detected as all-OA but DOIs don't work now
    override_dict['10.14800/scti.232'] = {
        'metadata_url': 'https://www.smartscitech.com/index.php/SCTI/article/view/828',
        'version': 'publishedVersion',
        'host_type_set': 'publisher',
    }

    # ticket 22945. first citeseerx link broken
    override_dict['10.1111/1467-8306.9302004'] = {
        'metadata_url': 'https://citeseerx.ist.psu.edu/viewdoc/summary?doi=10.1.1.109.1825',
        'pdf_url': 'https://citeseerx.ist.psu.edu/viewdoc/download?doi=10.1.1.109.1825&rep=rep1&type=pdf',
        'version': 'submittedVersion',
        'host_type_set': 'repository',
        'evidence': 'oa repository (via free pdf)',
    }

    # ticket 22967. first citeseerx link is slide deck
    override_dict['10.1109/msp.2010.936019'] = {
        'metadata_url': 'http://citeseerx.ist.psu.edu/viewdoc/summary?doi=10.1.1.470.8283',
        'pdf_url': 'http://www1.se.cuhk.edu.hk/~manchoso/papers/sdrapp-SPM.pdf',
        'version': 'acceptedVersion',
        'host_type_set': 'repository',
        'evidence': 'oa repository (via free pdf)',
    }

    # ticket 23017. can't scrape cairn
    override_dict['10.3917/sr.035.0007'] = {
        'metadata_url': 'https://doi.org/10.3917/sr.035.0007',
        'version': 'publishedVersion',
        'host_type_set': 'publisher',
        'license': 'cc-by-nc-nd',
    }

    # ticket 23017. can't scrape cairn
    override_dict['10.3917/sr.039.0119'] = {
        'metadata_url': 'https://doi.org/10.3917/sr.039.0119',
        'version': 'publishedVersion',
        'host_type_set': 'publisher',
        'license': 'cc-by-nc-nd',
    }

    # ticket 23020
    override_dict['10.3847/2041-8213/abe4de'] = {
        'metadata_url': 'https://doi.org/10.3847/2041-8213/abe4de',
        'version': 'publishedVersion',
        'host_type_set': 'publisher',
        'license': 'cc-by',
    }

    # ticket 23020
    override_dict['10.3847/2041-8213/abe71d'] = {
        'metadata_url': 'https://doi.org/10.3847/2041-8213/abe71d',
        'version': 'publishedVersion',
        'host_type_set': 'publisher',
        'license': 'cc-by',
    }

    # ticket 23020
    override_dict['10.3847/2041-8213/abed53'] = {
        'metadata_url': 'https://doi.org/10.3847/2041-8213/abed53',
        'version': 'publishedVersion',
        'host_type_set': 'publisher',
        'license': 'cc-by',
    }

    # ticket 23020
    override_dict['10.3847/2041-8213/abee6a'] = {
        'metadata_url': 'https://doi.org/10.3847/2041-8213/abee6a',
        'version': 'publishedVersion',
        'host_type_set': 'publisher',
        'license': 'cc-by',
    }

    # ticket 1025
    # WOS user says full article isn't available
    override_dict['10.1016/j.fuel.2019.116234'] = {}

    # ticket 215
    # doi.org links point to wrong article
    override_dict["10.1515/res-2016-0002"] = {}

    # ticket 584
    # repo match to dissertation with same title and author
    override_dict["10.3726/978-3-0343-2544-8"] = {}
    # book front matter
    override_dict["10.1007/978-3-319-78349-9"] = {}

    # ticket 594
    override_dict["10.1016/j.chemgeo.2016.02.020"] = {}

    # ticket 240 part 2. mislabeled in repository.
    override_dict["10.1111/eip.12323"] = {}

    # ticket 928. CC license in references.
    override_dict['10.1007/s11012-016-0472-5'] = {}

    # ticket 968. CC license for dataset.
    override_dict['10.1007/s12275-020-9536-2'] = {}

    # ticket 966. PDF link only works once.
    override_dict['10.1093/ee/nvz159'] = {}

    # ticket 1371. someone doesn't like green OA
    override_dict['10.1007/s10798-019-09554-0'] = {}

    # ticket 6937. bad license info on page
    override_dict['10.1016/j.breast.2015.07.036'] = {}

    # ticket 22163. doing a favor.
    override_dict['10.1016/j.energy.2015.06.127'] = {}

    # ticket 22794. page and metadata have license
    override_dict['10.1515/pac-2020-0702'] = {}

    # ticket 22791
    override_dict['10.1038/s41574-020-00451-4'] = {}

    # ticket 23164
    override_dict['10.24920/003522'] = {}

    # ticket 23293, bad license on bottom of publisher page
    override_dict['10.1016/j.matpr.2020.04.809'] = {}

    # ticket 22636
    override_dict['10.1007/978-981-15-4814-7'] = {
        'metadata_url': 'https://doi.org/10.1007/978-981-15-4814-7',
        'version': 'publishedVersion',
        'host_type_set': 'publisher',
        'evidence': 'open (via free pdf)',
    }

    # ticket 23094, broken doi resolution
    override_dict['10.12658/m0624'] = {
        'metadata_url': 'https://insanvetoplum.org/en/issues/11-2/m0624',
        'pdf_url': 'https://insanvetoplum.org/content/6-sayilar/28-11-2/6-m0624/peksan.pdf',
        'version': 'publishedVersion',
        'host_type_set': 'publisher',
        'evidence': 'oa journal (via doaj)',
        'license': 'cc-by-nc-nd',
    }

    override_dict['10.12658/m0622'] = {
        'metadata_url': 'https://insanvetoplum.org/en/issues/11-2/m0622',
        'pdf_url': 'https://insanvetoplum.org/content/6-sayilar/28-11-2/5-m0622/kose-tugsuz.pdf',
        'version': 'publishedVersion',
        'host_type_set': 'publisher',
        'evidence': 'oa journal (via doaj)',
        'license': 'cc-by-nc-nd',
    }

    override_dict['10.12658/m0617'] = {
        'metadata_url': 'https://insanvetoplum.org/en/issues/11-2/m0617',
        'pdf_url': 'https://insanvetoplum.org/content/6-sayilar/28-11-2/2-m0617/cevizli-bilen.pdf',
        'version': 'publishedVersion',
        'host_type_set': 'publisher',
        'evidence': 'oa journal (via doaj)',
        'license': 'cc-by-nc-nd',
    }

    override_dict['10.12658/m0618'] = {
        'metadata_url': 'https://insanvetoplum.org/en/issues/11-2/m0618',
        'pdf_url': 'https://insanvetoplum.org/content/6-sayilar/28-11-2/3-m0618/tirgil-aygun1.pdf',
        'version': 'publishedVersion',
        'host_type_set': 'publisher',
        'evidence': 'oa journal (via doaj)',
        'license': 'cc-by-nc-nd',
    }

    override_dict['10.12658/m0626'] = {
        'metadata_url': 'https://insanvetoplum.org/en/issues/11-2/m0626',
        'pdf_url': 'https://insanvetoplum.org/content/6-sayilar/28-11-2/8-m0626/ozcan-mercan.pdf',
        'version': 'publishedVersion',
        'host_type_set': 'publisher',
        'evidence': 'oa journal (via doaj)',
        'license': 'cc-by-nc-nd',
    }

    override_dict['10.12658/m0619'] = {
        'metadata_url': 'https://insanvetoplum.org/en/issues/11-2/m0619',
        'pdf_url': 'https://insanvetoplum.org/content/6-sayilar/28-11-2/4-m0619/valiyev.pdf',
        'version': 'publishedVersion',
        'host_type_set': 'publisher',
        'evidence': 'oa journal (via doaj)',
        'license': 'cc-by-nc-nd',
    }

    override_dict['10.12658/m0625'] = {
        'metadata_url': 'https://insanvetoplum.org/en/issues/11-2/m0625',
        'pdf_url': 'https://insanvetoplum.org/content/6-sayilar/28-11-2/7-m0625/yelpaze.pdf',
        'version': 'publishedVersion',
        'host_type_set': 'publisher',
        'evidence': 'oa journal (via doaj)',
        'license': 'cc-by-nc-nd',
    }

    override_dict['10.12658/m0610'] = {
        'metadata_url': 'https://insanvetoplum.org/en/issues/11-2/m0610',
        'pdf_url': 'https://insanvetoplum.org/content/6-sayilar/28-11-2/1-m0610/kizilkaya.pdf',
        'version': 'publishedVersion',
        'host_type_set': 'publisher',
        'evidence': 'oa journal (via doaj)',
        'license': 'cc-by-nc-nd',
    }

    # end ticket 23094

    # ticket 23326. whole issue is on one page so can't scrape. but fix the one they asked about.
    override_dict['10.31901/24566608.2020/71.1-3.3252'] = {
        'metadata_url': 'https://doi.org/10.31901/24566608.2020/71.1-3.3252',
        'pdf_url': 'http://krepublishers.com/02-Journals/JHE/JHE-71-0-000-20-Web/JHE-71-1-3-000-20-Abst-PDF/JHE-71-1-3-127-20-3252-Deepa-R/JHE-71-1-3-127-20-3252-Deepa-R-Tx[14].pdf',
        'version': 'publishedVersion',
        'host_type_set': 'publisher',
        'evidence': 'oa journal (via observed oa rate)',
    }

    override_dict['10.1080/1097198x.2020.1752084'] = {}

    override_dict['10.1016/j.matpr.2020.09.186'] = {}  # ticket 23203

    # ticket 22892, doi resolution is wrong
    # is https://www.journalofhospitalmedicine.com/jhospmed/article/189543/hospital-medicine/you-cant-have-it-all-experience-academic-hospitalists
    # should be https://www.journalofhospitalmedicine.com/jhospmed/article/189545/hospital-medicine/barriers-earlier-hospital-discharge-what-matters-most
    override_dict['10.12788/jhm.3094'] = {}

    # ticket 535
    # book & chapters listed at https://www.brepolsonline.net/doi/book/10.1484/M.RELMIN-EB.6.09070802050003050502050201
    for doi in ['10.1484/M.RELMIN-EB.6.09070802050003050502050201'] + ['10.1484/M.RELMIN-EB.5.1038' + str(n) for n in range(59, 76)]:
        override_dict[doi] = {
            "pdf_url": "https://www.doabooks.org/doab?func=fulltext&uiLanguage=en&rid=23027",
            "version": "publishedVersion",
            "host_type_set": "repository"
        }

    # book & chapters listed at https://www.brepolsonline.net/doi/book/10.1484/M.RELMIN-EB.5.109256
    for doi in ['10.1484/M.RELMIN-EB.5.109256'] + list(['10.1484/M.RELMIN-EB.5.1091' + str(n) for n in range(58, 70)]):
        override_dict[doi] = {
            "pdf_url": "https://www.doabooks.org/doab?func=fulltext&uiLanguage=en&rid=26957",
            "version": "publishedVersion",
            "host_type_set": "repository"
        }

    # book & chapters listed at https://www.brepolsonline.net/doi/book/10.1484/M.RELMIN-EB.5.108025
    for doi in ['10.1484/M.RELMIN-EB.5.108025'] + list(['10.1484/M.RELMIN-EB.5.1084' + str(n) for n in range(35, 51)]):
        override_dict[doi] = {
            "pdf_url": "https://www.doabooks.org/doab?func=fulltext&uiLanguage=en&rid=26953",
            "version": "publishedVersion",
            "host_type_set": "repository"
        }

    # book & chapters listed at https://www.brepolsonline.net/doi/book/10.1484/M.RELMIN-EB.6.09070802050003050500050207
    for doi in ['10.1484/M.RELMIN-EB.6.09070802050003050500050207'] + list(['10.1484/M.RELMIN-EB.1.1018' + str(n) for n in range(74, 92)]):
        override_dict[doi] = {
            "pdf_url": "https://www.doabooks.org/doab?func=fulltext&uiLanguage=en&rid=23029",
            "version": "publishedVersion",
            "host_type_set": "repository"
        }

    # book & chapters listed at https://www.brepolsonline.net/doi/book/10.1484/M.RELMIN-EB.5.108940
    for doi in ['10.1484/M.RELMIN-EB.5.108940'] + list(['10.1484/M.RELMIN-EB.5.1093' + str(n) for n in range(46, 60)]):
        override_dict[doi] = {
            "pdf_url": "https://www.doabooks.org/doab?func=fulltext&uiLanguage=en&rid=26960",
            "version": "publishedVersion",
            "host_type_set": "repository"
        }

    # book & chapters listed at https://www.brepolsonline.net/doi/book/10.1484/M.RELMIN-EB.6.09070802050003050408050408
    for doi in ['10.1484/M.RELMIN-EB.6.09070802050003050408050408'] + list(['10.1484/M.RELMIN-EB.1.1018' + str(n) for n in range(10, 27)]):
        override_dict[doi] = {
            "pdf_url": "https://www.doabooks.org/doab?func=fulltext&uiLanguage=en&rid=25736",
            "version": "publishedVersion",
            "host_type_set": "repository"
        }

    # book & chapters listed at https://www.brepolsonline.net/action/showBook?doi=10.1484%2FM.RELMIN-EB.5.106169
    for doi in ['10.1484/M.RELMIN-EB.5.106169'] + list(['10.1484/M.RELMIN-EB.4.000' + str(n).zfill(2) for n in range(2, 15)]):
        override_dict[doi] = {
            "pdf_url": "https://www.doabooks.org/doab?func=fulltext&uiLanguage=en&rid=23028",
            "version": "publishedVersion",
            "host_type_set": "repository"
        }

    # book & chapters listed at https://www.brepolsonline.net/doi/book/10.1484/M.RELMIN-EB.5.109274
    for doi in ['10.1484/M.RELMIN-EB.5.109274'] + list(['10.1484/M.RELMIN-EB.5.111' + str(n) for n in range(590, 615)]):
        override_dict[doi] = {
            "pdf_url": "https://www.doabooks.org/doab?func=fulltext&uiLanguage=en&rid=26954",
            "version": "publishedVersion",
            "host_type_set": "repository"
        }

    # book & chapters listed at https://www.brepolsonline.net/action/showBook?doi=10.1484/M.RELMIN-EB.5.112302
    for doi in ['10.1484/M.RELMIN-EB.5.112302'] + list(['10.1484/M.RELMIN-EB.5.1115' + str(n) for n in range(13, 29)]):
        override_dict[doi] = {
            "pdf_url": "https://www.doabooks.org/doab?func=fulltext&uiLanguage=en&rid=26961",
            "version": "publishedVersion",
            "host_type_set": "repository"
        }

    override_dict["10.1016/s1474-4422(19)30285-6"] = {
        "metadata_url": "http://hdl.handle.net/2066/207798",
        "version": "publishedVersion",
        "host_type_set": "repository",
        "evidence": "oa repository (manual)"
    }

    # ticket 23115
    override_dict["10.3847/1538-4357/abfb62"] = {
        "metadata_url": "https://doi.org/10.3847/1538-4357/abfb62",
        "version": "publishedVersion",
        "host_type_set": "publisher",
        "evidence": "open (via page says license)",
        "license": "cc-by",
    }

    # ticket 23357
    override_dict["10.4314/tjpr.v19i2.20"] = {
        "metadata_url": "https://www.tjpr.org/home/abstract.php?id=2776",
        "version": "publishedVersion",
        "host_type_set": "publisher",
        "evidence": "oa journal (via doaj)",
        "license": "cc-by",
    }

    # ticket 23365
    override_dict["10.5604/01.3001.0015.0242"] = {
        "metadata_url": "https://doi.org/10.5604/01.3001.0015.0242",
        "pdf_url": "https://archivesmse.org/api/files/download/1678754.pdf",
        "version": "publishedVersion",
        "evidence": "open (via free pdf)",
        "host_type_set": "publisher",
    }

    # ticket 23444
    override_dict["10.1053/eupc.2001.0173"] = {
        "metadata_url": "https://infoscience.epfl.ch/record/154915/files/2001_Seeck_EP_symptomatic%20postictal%20cardiac%20asystole%20in%20a%20young%20patient%20with%20parietal%20seizures.pdf",
        "pdf_url": "https://infoscience.epfl.ch/record/154915/files/2001_Seeck_EP_symptomatic%20postictal%20cardiac%20asystole%20in%20a%20young%20patient%20with%20parietal%20seizures.pdf",
        "version": "submittedVersion",
        "evidence": "oa repository (via OAI-PMH doi match)",
        "host_type_set": "repository"
    }

    # ticket 23479
    override_dict["10.1002/14651858.cd011772.pub2"] = {
        "metadata_url": "https://doi.org/10.1002/14651858.cd011772.pub2",
        "version": "publishedVersion",
        "host_type_set": "publisher"
    }

    # ticket 23654
    override_dict["10.31901/24566772.2015/09.01.04"] = {
        "metadata_url": "https://doi.org/10.31901/24566772.2015/09.01.04",
        "pdf_url": "http://krepublishers.com/02-Journals/S-EM/EM-09-0-000-15-Web/S-EM-09-1-15-Abst-PDF/S-EM-9-1-025-339-15-Ekiyor-A/S-EM-9-1-025-339-15-Ekiyor-A-Tx%5B4%5D.pdf",
        "version": "publishedVersion",
        "host_type_set": "publisher"
    }

    # ticket 23751, broken DOI
    override_dict["10.1016/s0185-2698(13)71815-4"] = {
        "metadata_url": "https://www.sciencedirect.com/science/article/pii/S0185269813718154",
        "version": "publishedVersion",
        "evidence": "oa journal (via observed oa rate)",
        "host_type_set": "publisher",
    }

    # ticket  23766, broken DOI
    override_dict["10.5935/1676-2444.20170032"] = {
        "metadata_url": "https://www.scielo.br/j/jbpml/a/wrvWHf6Tm78PxGpb8rHnTsN/?lang=en",
        "version": "publishedVersion",
        "evidence": "oa journal (via doaj)",
        "license": "cc-by",
        "host_type_set": "publisher",
    }

    # ticket 23864, broken DOI
    override_dict["10.32604/jrm.2020.011462"] = {
        "metadata_url": "https://www.techscience.com/jrm/v8n11/40268",
        "version": "publishedVersion",
        "evidence": "open (via page says license)",
        "license": "cc-by",
        "host_type_set": "publisher",
    }

    # ticket 23865, broken DOI
    override_dict["10.32604/jrm.2020.011453"] = {
        "metadata_url": "https://www.techscience.com/jrm/v8n11/40269",
        "version": "publishedVersion",
        "evidence": "open (via page says license)",
        "license": "cc-by",
        "host_type_set": "publisher",
    }

    # ticket 23940, licenced but not on publisher site
    override_dict["10.1007/978-3-319-66659-4_4"] = {
        "metadata_url": "https://hdl.handle.net/2043/26825",
        "pdf_url": "https://mau.diva-portal.org/smash/get/diva2:1406951/FULLTEXT01.pdf",
        "version": "publishedVersion",
        "evidence": "oa repository (via OAI-PMH title and first author match)",
        "license": "cc-by",
        "host_type_set": "repository",
    }

    # ticket 23947
    override_dict["10.4303/iep/e101203"] = {
        "metadata_url": "https://www.omicsonline.org/open-access/gaseous-pollutants-formation-and-their-harmful-effects-on-health-and-environment.php?aid=15178",
        "host_type_set": "publisher",
        "evidence": "open (via page says license)",
        "license": "cc-by",
        "version": "publishedVersion",
    }

    # ticket 23975, need to find an OA label for this journal
    override_dict["10.7202/1037312ar"] = {
        "metadata_url": "https://doi.org/10.7202/1037312ar",
        "host_type_set": "publisher",
        "version": "publishedVersion",
        "evidence": "open (via free article)",
    }

    # ticket 24006, page has license but it's not open
    override_dict['10.1007/s12440-021-00141-1'] = {}

    # ticket 24027
    override_dict['10.1016/j.chb.2018.02.003'] = {
        'metadata_url': 'https://www.researchgate.net/publication/323000147_Sexting_Among_Adolescents_A_Nuanced_and_Gendered_Online_Challenge_for_Young_People',
        'host_type_set': 'repository',
        'version': 'submittedVersion',
        'evidence': 'oa repository (manual)'
    }

    # ticket 24066, correction uploaded to PMC but not to publisher
    override_dict['10.20524/aog.2020.0518'] = {
        'metadata_url': 'https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7406818',
        'pdf_url': 'https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7406818/pdf/AnnGastroenterol-33-508.pdf',
        'host_type_set': 'repository',
        'evidence': 'oa repository (via pmcid lookup)',
        'version': 'publishedVersion',
    }

    # ticket 24125, show preprint from SSRN
    override_dict['10.1515/rle-2018-0067'] = {
        'metadata_url': 'https://doi.org/10.2139/ssrn.3246929',
        'host_type_set': 'repository',
        'evidence': 'oa repository (manual)',
        'version': 'submittedVersion',
    }

    # ticket 24109, wrong oa location
    override_dict['10.1037/0033-295X.105.1.158'] = {}

    # ticket 24096, wrong oa location
    override_dict['10.1108/BFJ-04-2021-0416'] = {}

    # ticket 24112, bad doi redirect
    override_dict['10.35935/edr/26.2616'] = {}

    # ticket 24120, incorrect oa location
    override_dict['10.1007/978-3-030-13334-4'] = {}

    # ticket 24207, incorrect oa location via repository
    override_dict['10.1007/978-3-319-55898-1'] = {}

    # ticket 24131, incorrect oa location via repository
    override_dict['10.1068/a3999'] = {}

    # ticket 24241, book chapter via repository
    override_dict['10.1093/oxfordhb/9780198729570.001.0001'] = {}

    # ticket 24204, found wrong pdf
    override_dict['10.1086/503923'] = {}

    # ticket 24204, found wrong pdf
    override_dict['10.1515/9783110536553'] = {}

    # ticket 24311, incorrect PDF via manuscript
    override_dict['10.1016/j.nima.2019.03.095'] = {}

    # ticket 24224, incorrect PDF via manuscript
    override_dict['10.30649/denta.v11i2.98'] = {}

    # ticket 24354, incorrect PDF file, should be closed
    override_dict['10.1163/1570065054300275'] = {}

    # ticket 24365, wrong location
    override_dict['10.1001/archpsyc.1994.03950010008002'] = {}

    # ticket 24316
    override_dict["10.1063/1.1676828"] = {
        "pdf_url": "https://aip.scitation.org/doi/pdf/10.1063/1.1676828",
        "version": "publishedVersion",
        "evidence": "open (via free pdf)",
        "host_type_set": "publisher",
    }
    override_dict["10.1016/s2215-0366(21)00258-3"] = {
        "pdf_url": "https://thelancet.com/action/showPdf?pii=S2215-0366%2821%2900258-3",
        "version": "publishedVersion",
        "evidence": "open (via free pdf)",
        "host_type_set": "publisher",
    }
    override_dict["10.1002/catl.30714"] = {
        "pdf_url": "https://onlinelibrary.wiley.com/doi/epdf/10.1002/catl.30714",
        "version": "publishedVersion",
        "evidence": "open (via free pdf)",
        "host_type_set": "publisher",
    }
    override_dict["10.1016/j.jadohealth.2021.06.026"] = {
        "pdf_url": "https://www.jahonline.org/action/showPdf?pii=S1054-139X%2821%2900339-6",
        "version": "publishedVersion",
        "evidence": "open (via free pdf)",
        "host_type_set": "publisher",
    }
    override_dict["10.1139/bcb-2016-0211"] = {
        "pdf_url": "https://cdnsciencepub.com/doi/pdf/10.1139/bcb-2016-0211",
        "version": "publishedVersion",
        "evidence": "open (via free pdf)",
        "host_type_set": "publisher",
    }
    override_dict["10.1287/orsc.1060.0189"] = {
        "pdf_url": "https://pubsonline.informs.org/doi/epdf/10.1287/orsc.1060.0189",
        "version": "publishedVersion",
        "evidence": "open (via free pdf)",
        "host_type_set": "publisher",
    }
    override_dict["10.1517/14656566.2013.808011"] = {
        "pdf_url": "https://www.tandfonline.com/doi/pdf/10.1517/14656566.2013.808011?needAccess=true",
        "version": "publishedVersion",
        "evidence": "open (via free pdf)",
        "host_type_set": "publisher",
    }
    override_dict["10.4141/cjss72-065"] = {
        "pdf_url": "https://cdnsciencepub.com/doi/pdf/10.4141/cjss72-065",
        "version": "publishedVersion",
        "evidence": "open (via free pdf)",
        "host_type_set": "publisher",
    }
    override_dict["10.1142/s0217979290001157"] = {
        "pdf_url": "https://www.worldscientific.com/doi/epdf/10.1142/S0217979290001157",
        "version": "publishedVersion",
        "evidence": "open (via free pdf)",
        "host_type_set": "publisher",
    }
    override_dict["10.1063/1.444450"] = {
        "pdf_url": "https://aip.scitation.org/doi/pdf/10.1063/1.444450",
        "version": "publishedVersion",
        "evidence": "open (via free pdf)",
        "host_type_set": "publisher",
    }
    override_dict["10.1002/adma.201570284"] = {
        "pdf_url": "https://onlinelibrary.wiley.com/doi/epdf/10.1002/adma.201570284",
        "version": "publishedVersion",
        "evidence": "open (via free pdf)",
        "host_type_set": "publisher",
    }

    # ticket 24395
    override_dict['10.4324/9781315212043'] = {}

    # ticket 24224
    override_dict['10.1007/978-88-470-3944-5'] = {}

    # ticket 24427
    override_dict['10.1007/978-3-030-69262-9'] = {}

    # ticket 24426
    override_dict['10.1007/978-981-15-0548-5'] = {}

    # ticket 24501
    override_dict['10.7312/negi14448'] = {}

    # ticket 5656744
    override_dict["10.3301/GFT.2010.01"] = {
        "metadata_url": "https://www.isprambiente.gov.it/it/pubblicazioni/periodici-tecnici/geological-field-trips/an-itinerary-through-proterozoic-to-holocene-rocks",
        "pdf_url": "https://www.isprambiente.gov.it/it/pubblicazioni/periodici-tecnici/geological-field-trips/resolveuid/95a7d4a397e4483b86299214b8351498",
        "version": "publishedVersion",
        "evidence": "open (via free pdf)",
        "host_type_set": "publisher",
    }

    override_dict["10.3301/GFT.2009.01"] = {
        "metadata_url": "https://www.isprambiente.gov.it/it/pubblicazioni/periodici-tecnici/geological-field-trips/the-laga-basin-stratigraphic-and-structural-setting",
        "pdf_url": "https://www.isprambiente.gov.it/it/pubblicazioni/periodici-tecnici/geological-field-trips/resolveuid/c8c98c95c8374512bc5f4c057e4d6ba5",
        "version": "publishedVersion",
        "evidence": "open (via free pdf)",
        "host_type_set": "publisher",
    }

    # ticket 24707
    override_dict['10.1111/sjop.12361'] = {}

    # ticket 24766
    override_dict['10.1080/07448481.2020.1740231'] = {}

    # ticket 24805
    override_dict['10.1007/978-3-030-88773-5'] = {}

    override_dict['10.1007/978-3-319-33228-4'] = {}

    override_dict['10.2307/749877'] = {}

    override_dict["10.1039/c5nr02694f"] = {
        "pdf_url": "http://ir.qibebt.ac.cn/bitstream/337004/6456/1/A%20V2O3-ordered%20mesoporous%20carbon%20composite%20with%20novel%20peroxidase-like%20activity%20towards%20the%20glucose%20colorimetric%20assay%e2%80%a0.pdf",
        "version": "publishedVersion",
        "host_type_set": "repository"
    }

    override_dict['10.7551/mitpress/10413.001.0001'] = {}

    override_dict['10.1002/pfi.4140410512'] = {}

    override_dict['10.1038/nclimate2301'] = {}

    override_dict['10.5840/studphaen20141411'] = {}

    override_dict["10.1007/978-0-387-93837-0"] = {}

    override_dict["10.1108/RPJ-02-2021-0039"] = {}

    override_dict["10.1007/978-3-642-34435-0"] = {
        "pdf_url": "https://link.springer.com/content/pdf/10.1007/978-3-642-34435-0.pdf",
        "version": "submittedVersion",
        "host_type_set": "repository"
    }
    override_dict["10.1007/978-3-662-45529-6"] = {
        "pdf_url": "https://link.springer.com/content/pdf/10.1007/978-3-662-45529-6.pdf",
        "version": "submittedVersion",
        "host_type_set": "repository"
    }
    override_dict["10.1007/978-3-662-59192-5"] = {
        "pdf_url": "https://link.springer.com/content/pdf/10.1007/978-3-662-59192-5.pdf",
        "version": "submittedVersion",
        "host_type_set": "repository"
    }

    # the use of this is counting on the doi keys being lowercase/canonical
    response = {}
    for k, v in override_dict.items():
        response[normalize_doi(k)] = v

    return response
