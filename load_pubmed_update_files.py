import csv
import gzip
import tempfile
from ftplib import FTP

from lxml import etree
from sqlalchemy import text

from app import db, logger

CSV_COLUMNS = ['pmid', 'doi', 'pmcid', 'pubmed_article_xml']


def retrieve_file(ftp_client, filename):
    local_filename = tempfile.mkstemp()[1]

    with open(local_filename, 'wb') as f:
        ftp_client.retrbinary(f'RETR {filename}', f.write)

    logger.info(f'retrieved {filename} as {local_filename}')
    return local_filename


def xml_to_csv(filename):
    articles = {}
    with gzip.open(filename, "rt") as f:
        xml = f.read()
        xml = xml.replace('\n', '')
        xml = xml.replace('<PubmedArticle>', '\n\n<PubmedArticle>')
        xml = xml.replace('</PubmedArticle>', '</PubmedArticle>\n\n')

        article_lines = [line for line in xml.split('\n') if '<PubmedArticle>' in line]

        for article_xml in article_lines:
            article = etree.fromstring(article_xml)

            pmid_node = article.find('.//PubmedData/ArticleIdList/ArticleId[@IdType="pubmed"]')
            pmid = pmid_node.text if pmid_node is not None else None

            if not pmid:
                continue

            doi_node = article.find('.//PubmedData/ArticleIdList/ArticleId[@IdType="doi"]')
            doi = doi_node.text if doi_node is not None else None

            pmcid_node = article.find('.//PubmedData/ArticleIdList/ArticleId[@IdType="pmc"]')
            pmcid = pmcid_node.text.lower() if pmcid_node is not None else None

            articles[pmid] = {
                'pmid': pmid,
                'doi': doi,
                'pmcid': pmcid,
                'pubmed_article_xml': article_xml
            }

    csv_filename = tempfile.mkstemp()[1]
    with open(csv_filename, 'wt') as f:
        csv_writer = csv.writer(f)
        for article in articles.values():
            csv_writer.writerow(article[k] for k in CSV_COLUMNS)

    logger.info(f'converted xml rows from {filename} to csv {csv_filename}')
    return csv_filename


def load_csv(csv_filename):
    db.session.rollback()

    logger.info(f'loading csv rows to temp table')
    db.session.execute(text('create temp table tmp_pubmed_raw (like recordthresher.pubmed_raw including all);'))

    cursor = db.session.connection().connection.cursor()
    with open(csv_filename, 'rt') as f:
        cursor.copy_expert(f'copy tmp_pubmed_raw ({",".join(CSV_COLUMNS)}) from stdin csv', f)

    logger.info(f'replacing rows in recordthresher.pubmed_raw')
    db.session.execute(text('delete from recordthresher.pubmed_raw where pmid in (select pmid from tmp_pubmed_raw);'))
    db.session.execute(text('insert into recordthresher.pubmed_raw (select * from tmp_pubmed_raw)'))

    db.session.commit()


def run():
    ftp = FTP('ftp.ncbi.nlm.nih.gov')
    ftp.login()
    ftp.cwd('/pubmed/updatefiles/')

    update_filenames = sorted([f for f in ftp.nlst() if f.endswith('.xml.gz')])[-2:]
    local_update_filenames = [retrieve_file(ftp, f) for f in update_filenames]

    ftp.quit()

    for update_filename in local_update_filenames:
        csv_filename = xml_to_csv(update_filename)
        load_csv(csv_filename)


if __name__ == "__main__":
    run()
