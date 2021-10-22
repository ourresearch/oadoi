import re

from recordthresher.record_maker import PmhRecordMaker
from recordthresher.util import normalize_author, parseland_parse, xml_tree


class RepecRecordMaker(PmhRecordMaker):
    @staticmethod
    def _is_specialized_record_maker(pmh_record):
        return (
            pmh_record.pmh_id and pmh_record.pmh_id.startswith('oai:RePEc:')
            and any(f'<dc:type>{item_type}</dc:type>' in pmh_record.api_raw for item_type in [
                'article', 'preprint', 'book'
            ])
        )

    @classmethod
    def _representative_page(cls, pmh_record):
        repec_handle = re.sub(r'^oai:', '', pmh_record.pmh_id)
        for repo_page in pmh_record.pages:
            if repo_page.url and repo_page.url.endswith(f'econpapers.repec.org/{repec_handle}'):
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

            first_type_element = pmh_xml_tree.find('.//type')
            if first_type_element is not None and first_type_element.text:
                record.genre = first_type_element.text

        if repo_page:
            if (pl_parse := parseland_parse(cls._parseland_api_url(repo_page), retry_seconds=10)) is not None:
                record.set_published_date(pl_parse['published_date'])
