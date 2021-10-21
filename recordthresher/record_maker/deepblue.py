from recordthresher.record_maker import PmhRecordMaker
from recordthresher.util import normalize_author, xml_tree


class DeepBlueRecordMaker(PmhRecordMaker):
    @staticmethod
    def _is_specialized_record_maker(pmh_record):
        return (
            pmh_record.pmh_id
            and pmh_record.pmh_id.startswith('oai:deepblue.lib.umich.edu:')
            and any(f'<dc:type>{item_type}</dc:type>' in pmh_record.api_raw for item_type in [
                'Article', 'Thesis', 'Technical Report', 'Working Paper',
            ])
        )

    @classmethod
    def _representative_page(cls, pmh_record):
        item_id = pmh_record.pmh_id.split(':')[-1]

        for repo_page in pmh_record.pages:
            if repo_page.url and repo_page.url.endswith(f'handle.net/{item_id}'):
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

            dates = pmh_xml_tree.findall('.//date')
            if dates and dates[-1].text:
                record.set_published_date(dates[-1].text)

            type_element = pmh_xml_tree.find('.//type')
            if type_element is not None and type_element.text:
                record.genre = type_element.text
