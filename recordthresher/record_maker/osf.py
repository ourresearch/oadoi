import re

from recordthresher.record_maker import CrossrefRecordMaker


class OsfRecordMaker(CrossrefRecordMaker):
    @staticmethod
    def _is_specialized_record_maker(pub):
        return re.search(r'/osf\.io/[a-z0-9]+$', pub.doi)
