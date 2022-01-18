from recordthresher.record_maker import CrossrefRecordMaker


class BiorxivRecordMaker(CrossrefRecordMaker):
    @staticmethod
    def _is_specialized_record_maker(pub):
        return pub.doi.startswith('10.1101/') and pub.genre == 'posted-content'

    @classmethod
    def _make_source_specific_record_changes(cls, record, pub):
        cls._merge_parseland_parse(record, pub)
