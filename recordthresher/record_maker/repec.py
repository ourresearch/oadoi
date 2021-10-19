from recordthresher.record_maker import PmhRecordMaker
from recordthresher.util import xml_tree


class RepecRecordMaker(PmhRecordMaker):
    @staticmethod
    def _is_specialized_record_maker(pmh_record):
        return pmh_record.pmh_id and pmh_record.pmh_id.startswith('oai:RePEc:')

    @classmethod
    def _make_source_specific_record_changes(cls, record, pmh_record, repo_page):
        pmh_xml_tree = xml_tree(pmh_record.api_raw)

        if pmh_xml_tree is not None:
            if (type_element := pmh_xml_tree.find('.//type')) is not None:
                record.genre = type_element.text
