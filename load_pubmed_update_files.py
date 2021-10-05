import csv
import gzip
import tempfile
from ftplib import FTP

from lxml import etree
from sqlalchemy import text

from app import db, logger


def retrieve_file(ftp_client, filename):
    local_filename = tempfile.mkstemp()[1]

    with open(local_filename, 'wb') as f:
        ftp_client.retrbinary(f'RETR {filename}', f.write)

    logger.info(f'retrieved {filename} as {local_filename}')
    return local_filename


def xml_gz_to_csv(xml_gz_filename):
    seen_pmids = set()

    csv_filename = tempfile.mkstemp()[1]
    with gzip.open(xml_gz_filename, "rb") as xml_file, open(csv_filename, 'wt') as csv_file:
        csv_writer = csv.writer(csv_file)

        for article_event, article_element in etree.iterparse(xml_file, tag="PubmedArticle", remove_blank_text=True):
            pmid_node = article_element.find('.//PubmedData/ArticleIdList/ArticleId[@IdType="pubmed"]')
            pmid = pmid_node.text if pmid_node is not None else None

            if not pmid or pmid in seen_pmids:
                continue

            seen_pmids.add(pmid)

            doi_node = article_element.find('.//PubmedData/ArticleIdList/ArticleId[@IdType="doi"]')
            doi = doi_node.text if doi_node is not None else None

            pmcid_node = article_element.find('.//PubmedData/ArticleIdList/ArticleId[@IdType="pmc"]')
            pmcid = pmcid_node.text.lower() if pmcid_node is not None else None

            references = article_element.findall('.//ReferenceList/Reference')
            for reference_no, reference in enumerate(references):
                reference.set('RecordthresherReferenceNo', str(reference_no + 1))

            authors = article_element.findall('.//AuthorList/Author')
            for author_no, author in enumerate(authors):
                author.set('RecordthresherAuthorNo', str(author_no + 1))

                author_affiliations = author.findall('.//AffiliationInfo/Affiliation')
                for author_affiliation_no, author_affiliation in enumerate(author_affiliations):
                    author_affiliation.set('RecordthresherAuthorAffiliationNo', str(author_affiliation_no + 1))

            article_element_string = etree.tostring(article_element, encoding='unicode')

            csv_writer.writerow([pmid, doi, pmcid, article_element_string])
            article_element.getparent().remove(article_element)

    logger.info(f'converted {len(seen_pmids)} articles from {xml_gz_filename} to csv {csv_filename}')
    return csv_filename


def load_csv(csv_filename):
    db.session.rollback()

    logger.info(f'loading csv rows to temp table')
    db.session.execute(text('create temp table tmp_pubmed_raw (like recordthresher.pubmed_raw including all);'))

    cursor = db.session.connection().connection.cursor()
    with open(csv_filename, 'rt') as f:
        cursor.copy_expert("copy tmp_pubmed_raw (pmid, doi, pmcid, pubmed_article_xml) from stdin csv", f)

    logger.info(f'replacing rows in recordthresher.pubmed_raw')
    db.session.execute(text('delete from recordthresher.pubmed_raw where pmid in (select pmid from tmp_pubmed_raw);'))
    db.session.execute(text('insert into recordthresher.pubmed_raw (select * from tmp_pubmed_raw)'))

    db.session.commit()


def start_ingest(remote_filename):
    return db.engine.execute(
        text('''
            insert into recordthresher.pubmed_update_ingest
            (filename, started) values (:filename, now())
            on conflict (filename) do update set started = now()
            where pubmed_update_ingest.finished is null and pubmed_update_ingest.started < now() - interval '4 hours'
            returning pubmed_update_ingest.filename;
        ''').bindparams(filename=remote_filename).execution_options(autocommit=True)
    ).scalar()


def finish_ingest(remote_filename):
    db.engine.execute(
        text(
            'update recordthresher.pubmed_update_ingest set finished = now() where filename = :filename'
        ).bindparams(filename=remote_filename).execution_options(autocommit=True)
    )


def new_ftp_client():
    ftp = FTP('ftp.ncbi.nlm.nih.gov')
    ftp.login()
    ftp.cwd('/pubmed/updatefiles/')
    return ftp


def run():
    ftp = new_ftp_client()
    remote_filenames = sorted([f for f in ftp.nlst() if f.endswith('.xml.gz')])
    ftp.quit()

    finished_filenames = [
        x[0] for x in
        db.engine.execute("select filename from recordthresher.pubmed_update_ingest where finished is not null").all()
    ]

    for remote_filename in remote_filenames:
        if remote_filename in finished_filenames:
            logger.info(f'skipping {remote_filename}')
            continue

        if start_ingest(remote_filename):
            logger.info(f'starting {remote_filename}')
            ftp = new_ftp_client()
            local_filename = retrieve_file(ftp, remote_filename)
            ftp.quit()
            csv_filename = xml_gz_to_csv(local_filename)
            load_csv(csv_filename)
            finish_ingest(remote_filename)
        else:
            logger.info(f'skipping {remote_filename}')


if __name__ == "__main__":
    run()
