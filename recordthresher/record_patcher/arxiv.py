from .patcher import PmhRecordPatcher
from recordthresher.util import normalize_author


class ArxivPatcher(PmhRecordPatcher):
    @classmethod
    def _should_patch_record(cls, record, pmh_record, repo_page):
        return pmh_record.pmh_id and pmh_record.pmh_id.startswith('oai:arXiv.org:')

    @classmethod
    def _patch_record(cls, record, pmh_record, repo_page):
        pmh_xml_tree = cls._xml_tree(pmh_record.api_raw)

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
