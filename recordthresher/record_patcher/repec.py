from .patcher import PmhRecordPatcher


class RepecPatcher(PmhRecordPatcher):
    @classmethod
    def _should_patch_record(cls, record, pmh_record, repo_page):
        return pmh_record.pmh_id and pmh_record.pmh_id.startswith('oai:RePEc:')

    @classmethod
    def _patch_record(cls, record, pmh_record, repo_page):
        pmh_xml_tree = cls._xml_tree(pmh_record.api_raw)

        if pmh_xml_tree is not None:
            if (type_element := pmh_xml_tree.find('.//type')) is not None:
                record.genre = type_element.text
