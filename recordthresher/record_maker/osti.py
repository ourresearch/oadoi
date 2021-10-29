from recordthresher.record_maker import PmhRecordMaker
from recordthresher.util import parseland_parse


class OstiRecordMaker(PmhRecordMaker):
    @staticmethod
    def _is_specialized_record_maker(pmh_record):
        return pmh_record and pmh_record.pmh_id and pmh_record.pmh_id.startswith('oai:osti.gov:')

    @classmethod
    def _representative_page(cls, pmh_record):
        item_id = pmh_record.pmh_id.split(':')[-1]

        for repo_page in pmh_record.pages:
            if repo_page.url and repo_page.url.endswith(f'osti.gov/biblio/{item_id}'):
                return repo_page

        return None

    @classmethod
    def _make_source_specific_record_changes(cls, record, pmh_record, repo_page):
        if (pl_parse := parseland_parse(cls._parseland_api_url(repo_page), retry_seconds=10)) is not None:
            record.set_authors(pl_parse['authors'])
            record.set_published_date(pl_parse['published_date'])
            record.genre = pl_parse['genre']
