from recordthresher.record_maker import PmhRecordMaker
from recordthresher.util import normalize_author, xml_tree


class UncCdrRecordMaker(PmhRecordMaker):
    @staticmethod
    def _is_specialized_record_maker(pmh_record):
        return pmh_record.pmh_id and pmh_record.pmh_id.startswith('cdr.lib.unc.edu:')

    @classmethod
    def _representative_page(cls, pmh_record):
        if '<dc:type>Article</dc:type>' in pmh_record.api_raw:
            for repo_page in pmh_record.pages:
                if 'doi.org/10.17615/' in repo_page.url:
                    return repo_page

        return None

    @classmethod
    def _make_source_specific_record_changes(cls, record, pmh_record, repo_page):
        pmh_xml_tree = xml_tree(pmh_record.api_raw)

        if pmh_xml_tree is not None:
            type_element = pmh_xml_tree.find('.//type')
            if type_element is not None and type_element.text:
                record.genre = type_element.text

            date_element = pmh_xml_tree.find('.//date')
            if date_element is not None and date_element.text:
                record.set_published_date(date_element.text)

            authors = []

            if (dc_tag := pmh_xml_tree.find('metadata/dc')) is not None:
                found_creators = False
                author = None

                for element in dc_tag.getchildren():
                    if element.tag == 'creator':
                        found_creators = True
                        if author:
                            authors.append(normalize_author(author))
                        author = {'raw': element.text, 'affiliation': []}
                    elif element.tag == 'contributor':
                        if author:
                            author['affiliation'].append({'name': element.text})
                    elif found_creators:
                        break

                if author:
                    authors.append(normalize_author(author))

            record.set_authors(authors)
