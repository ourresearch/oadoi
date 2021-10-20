from recordthresher.record_maker import PmhRecordMaker


class DoajRecordMaker(PmhRecordMaker):
    @staticmethod
    def _is_specialized_record_maker(pmh_record):
        return pmh_record.pmh_id and pmh_record.pmh_id.startswith('oai:doaj.org/article:')

    @classmethod
    def _make_source_specific_record_changes(cls, record, pmh_record, repo_page):
        pass
