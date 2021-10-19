import re

from recordthresher.record_maker import CrossrefRecordMaker


class OsfRecordMaker(CrossrefRecordMaker):
    @staticmethod
    def _is_specialized_record_maker(pub):
        return re.search(r'/osf\.io/[a-z0-9]+$', pub.doi)

    @classmethod
    def _make_source_specific_record_changes(cls, record, pub):
        record.is_oa = True
        record.oa_date = pub.published_date
        record.open_version = 'submittedVersion'
