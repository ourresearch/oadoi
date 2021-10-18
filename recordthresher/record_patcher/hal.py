from .patcher import PmhRecordPatcher


class HalPatcher(PmhRecordPatcher):
    @classmethod
    def _should_patch_record(cls, record, pmh_record, repo_page):
        return pmh_record.pmh_id and pmh_record.pmh_id.startswith('oai:HAL:')

    @classmethod
    def _patch_record(cls, record, pmh_record, repo_page):
        pmh_xml_tree = cls._xml_tree(pmh_record.api_raw)

        if pmh_xml_tree is not None:
            for type_element in pmh_xml_tree.xpath('.//type'):
                if type_element.text and type_element.text.startswith('info:eu-repo/semantics/'):
                    record.genre = type_element.text
                    break

            first_date_element = pmh_xml_tree.find('.//date')
            if first_date_element is not None and first_date_element.text:
                record.set_published_date(first_date_element.text)

        if repo_page:
            if (pl_authors := cls._parseland_authors(repo_page)) is not None:
                record.authors = pl_authors
