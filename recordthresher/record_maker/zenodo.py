from recordthresher.record_maker import PmhRecordMaker
from recordthresher.util import parseland_parse, xml_tree


class ZenodoRecordMaker(PmhRecordMaker):
    @staticmethod
    def _is_specialized_record_maker(pmh_record):
        return (
            pmh_record and pmh_record.pmh_id and pmh_record.pmh_id.startswith('oai:zenodo.org:')
            and any(f'<dc:type>info:eu-repo/semantics/{item_type}</dc:type>' in pmh_record.api_raw for item_type in [
                'article', 'conferencePaper', 'report', 'book', 'doctoralThesis', 'preprint', 'workingPaper'
            ])
        )

    @classmethod
    def _representative_page(cls, pmh_record):
        item_id = pmh_record.pmh_id.split(':')[-1]

        for repo_page in pmh_record.pages:
            if repo_page.url and repo_page.url.endswith(f'zenodo.org/record/{item_id}'):
                return repo_page

        return None

    @classmethod
    def _make_source_specific_record_changes(cls, record, pmh_record, repo_page):
        pmh_xml_tree = xml_tree(pmh_record.api_raw)

        if pmh_xml_tree is not None:
            date = pmh_xml_tree.find('.//date')
            if date is not None and date.text:
                record.set_published_date(date.text)

            for type_element in pmh_xml_tree.xpath('.//type'):
                if type_element.text and type_element.text.startswith('info:eu-repo/semantics/'):
                    record.genre = type_element.text
                    break

        if (pl_parse := parseland_parse(cls._parseland_api_url(repo_page), retry_seconds=10)) is not None:
            record.set_authors(pl_parse['authors'])
