from recordthresher.record_maker import PmhRecordMaker
from recordthresher.util import normalize_author, xml_tree


class DoajRecordMaker(PmhRecordMaker):
    @staticmethod
    def _is_specialized_record_maker(pmh_record):
        return pmh_record.pmh_id and pmh_record.pmh_id.startswith('oai:doaj.org/article:')

    @classmethod
    def _representative_page(cls, pmh_record):
        doaj_id = pmh_record.pmh_id.split(':')[-1]
        for repo_page in pmh_record.pages:
            if repo_page.url.endswith(f'doaj.org/article/{doaj_id}'):
                return repo_page

        return None

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

            first_type_element = pmh_xml_tree.find('.//type')
            if first_type_element is not None and first_type_element.text:
                record.genre = first_type_element.text
