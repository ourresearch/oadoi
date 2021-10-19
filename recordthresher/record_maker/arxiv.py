from recordthresher.record_maker import PmhRecordMaker
from recordthresher.util import normalize_author, xml_tree


class ArxivRecordMaker(PmhRecordMaker):
    @staticmethod
    def _is_specialized_record_maker(pmh_record):
        return pmh_record.pmh_id and pmh_record.pmh_id.startswith('oai:arXiv.org:')

    @classmethod
    def _make_source_specific_record_changes(cls, record, pmh_record, repo_page):
        pmh_xml_tree = xml_tree(pmh_record.api_raw)

        if pmh_xml_tree is not None:
            authors = []

            for author_element in pmh_xml_tree.xpath('.//creator'):
                if author_element.text:
                    authors.append(normalize_author({'raw': author_element.text}))

            record.set_authors(authors)

            first_date_element = pmh_xml_tree.find('.//date')
            if first_date_element is not None and first_date_element.text:
                record.set_published_date(first_date_element.text)

            first_description_element = pmh_xml_tree.find('.//description')
            if first_description_element is not None and first_description_element.text:
                record.abstract = first_description_element.text

            record.genre = 'preprint'

            # can't use scrape archive as an html page indicator because we don't scrape arxiv
            record.record_webpage_url = repo_page.scrape_metadata_url
