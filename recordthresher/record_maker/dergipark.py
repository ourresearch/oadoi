import re

from recordthresher.record_maker import PmhRecordMaker
from recordthresher.util import parseland_parse
from recordthresher.util import xml_tree


class DergiparkRecordMaker(PmhRecordMaker):
    @staticmethod
    def _is_specialized_record_maker(pmh_record):
        return pmh_record and pmh_record.pmh_id and pmh_record.pmh_id.startswith('oai:dergipark.org.tr:')

    @classmethod
    def _representative_page(cls, pmh_record):
        for repo_page in pmh_record.pages:
            if re.search(r'dergipark\.org\.tr/[^/]+/pub/', repo_page.url):
                return repo_page

        return None

    @classmethod
    def _make_source_specific_record_changes(cls, record, pmh_record, repo_page):
        if (pmh_xml_tree := xml_tree(pmh_record.api_raw)) is not None:
            for type_element in pmh_xml_tree.xpath('.//type'):
                if type_element.text and type_element.text.startswith('info:eu-repo/semantics/'):
                    record.genre = type_element.text
                    break

            first_date_element = pmh_xml_tree.find('.//date')
            if first_date_element is not None and first_date_element.text:
                record.set_published_date(first_date_element.text)

        if (pl_parse := parseland_parse(cls._parseland_api_url(repo_page), retry_seconds=10)) is not None:
            record.set_authors(pl_parse['authors'])
