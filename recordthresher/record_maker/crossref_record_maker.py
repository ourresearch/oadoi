import datetime
import hashlib
import math
import re
import uuid
from urllib.parse import quote

import shortuuid

from app import db
from oa_page import doi_repository_ids
from page import RepoPage
from recordthresher.crossref_doi_record import CrossrefDoiRecord
from recordthresher.util import normalize_author, cleanup_affiliation
from recordthresher.util import normalize_citation
from recordthresher.util import parseland_parse
from util import normalize, normalize_title
from .record_maker import RecordMaker


class CrossrefRecordMaker(RecordMaker):
    @staticmethod
    def _is_specialized_record_maker(pub):
        return False

    @classmethod
    def make_record(cls, pub):
        return cls._dispatch(pub=pub)

    @staticmethod
    def _parseland_api_url(pub):
        return f'https://parseland.herokuapp.com/parse-publisher?doi={pub.id}'

    @classmethod
    def record_id_for_pub(cls, pub):
        return shortuuid.encode(
            uuid.UUID(bytes=hashlib.sha256(
                f'crossref_doi:{pub.id}'.encode('utf-8')).digest()[0:16])
        )

    @classmethod
    def find_record(cls, pub):
        if record_id := cls.record_id_for_pub(pub):
            return CrossrefDoiRecord.query.get(record_id)

    @classmethod
    def _make_record_impl(cls, pub):
        if pub.id and pub.id == '10.18034/abcjar.v10i1.556':
            # redacted
            return None

        record = cls.find_record(pub) or CrossrefDoiRecord(
            id=cls.record_id_for_pub(pub))

        record.title = pub.title

        record.normalized_title = normalize_title(record.title)
        authors = [normalize_author(author) for author in
                   pub.authors] if pub.authors else []
        record.set_jsonb('authors', authors)

        record.doi = pub.id
        record.abstract = pub.abstract_from_crossref or None
        record.published_date = pub.issued or pub.created or pub.crossref_published or pub.deposited

        if not record.published_date:
            return None

        record.genre = pub.genre

        pub_crossref_api_raw = pub.crossref_api_raw_new or {}

        citations = [
            normalize_citation(ref)
            for ref in pub_crossref_api_raw.get('reference', [])
        ]
        record.set_jsonb('citations', citations)
        record.set_jsonb('funders', pub.crossref_api_modified.get('funder', []))

        record.record_webpage_url = pub.url
        record.set_jsonb('journal_issns', pub.issns)
        record.journal_issn_l = pub.issn_l

        if not record.title and record.genre == 'grant':
            grant_titles = set()
            for project in pub_crossref_api_raw.get('project', []):
                for project_title in project.get('project-title', []):
                    title_string = project_title.get('title')
                    if title_string:
                        grant_titles.add(title_string)

            if grant_titles:
                record.title = sorted(list(grant_titles), key=len)[-1]

        if not record.journal_issn_l:
            doi_repo_page = RepoPage.query.filter(
                RepoPage.doi == pub.id,
                RepoPage.endpoint_id.in_(doi_repository_ids)
            ).first()

            if doi_repo_page:
                record.repository_id = doi_repo_page.endpoint_id

        # record.journal_id = pub.openalex_journal_id
        record.venue_name = pub.journal or pub.crossref_api_raw.get('event', {}).get('name')
        record.publisher = pub.publisher
        record.is_retracted = pub.is_retracted

        record.issue = pub.issue
        record.volume = pub.volume
        record.first_page = pub.first_page
        record.last_page = pub.last_page

        if record.genre and 'book' in record.genre and record.publisher:
            record.normalized_book_publisher = re.sub(r'[^\w]|[\d]', '',
                                                      record.publisher.lower())

        crossref_institution = pub_crossref_api_raw.get('institution', [])

        if not isinstance(crossref_institution, list):
            crossref_institution = [crossref_institution]

        for ci in crossref_institution:
            if 'place' in ci and not isinstance(ci['place'], list):
                ci['place'] = [ci['place']]
            if 'department' in ci and not isinstance(ci['department'], list):
                ci['department'] = [ci['department']]
            if 'acronym' in ci and not isinstance(ci['acronym'], list):
                ci['acronym'] = [ci['acronym']]

        record.set_jsonb('institution_host', crossref_institution)

        record.record_webpage_archive_url = pub.landing_page_archive_url() if pub.doi_landing_page_is_archived else None

        record.record_structured_url = f'https://api.crossref.org/v1/works/{quote(pub.id)}'
        record.record_structured_archive_url = f'https://api.unpaywall.org/crossref_api_cache/{quote(pub.id)}'

        pub.recalculate(quiet=True, ask_preprint=False)

        doi_oa_location = None
        for oa_location in pub.all_oa_locations:
            if oa_location.metadata_url == pub.url and not oa_location.endpoint_id:
                doi_oa_location = oa_location

        if doi_oa_location:
            record.work_pdf_url = doi_oa_location.pdf_url
            record.is_work_pdf_url_free_to_read = True if doi_oa_location.pdf_url else None
        else:
            record.work_pdf_url = None
            record.is_work_pdf_url_free_to_read = None

        if (local_lookup := pub.ask_local_lookup()) and not local_lookup[
            'is_future']:
            record.open_license = local_lookup['location'].license
            record.open_version = local_lookup['location'].version
            record.is_oa = True
        elif hybrid_scrape := pub.ask_hybrid_scrape():
            record.open_license = hybrid_scrape.license
            record.open_version = hybrid_scrape.version
            record.is_oa = True

        cls._make_source_specific_record_changes(record, pub)

        record.flag_modified_jsonb()

        if db.session.is_modified(record):
            record.updated = datetime.datetime.utcnow().isoformat()

        return record

    @classmethod
    def _match_affiliation(cls, aff, other_affs):
        # Splitting by non-alpha chars (\W) is automatically going to trim/strip commas, spaces, periods, etc from each word
        aff_capitalized_words = set()

        if aff:
            aff_capitalized_words = set(
                [word for word in re.split(r'\W', aff) if
                 word and word[0].isupper()])
        best_match_idx = -1
        highest_match_count = 0
        for i, other_aff in enumerate(other_affs):
            if not other_aff:
                continue
            # Sometimes affiliation strings are all uppercase i.e. GOOGLE INC.
            # Don't want to use word.istitle() for this reason
            other_capitalized_words = set(
                [word for word in re.split(r'\W', other_aff) if
                 word and word[0].isupper()])
            matches = [word for word in other_capitalized_words if
                       word in aff_capitalized_words]
            match_count = len(matches)
            if match_count > highest_match_count:
                best_match_idx = i
                highest_match_count = match_count
        return best_match_idx

    @classmethod
    def _match_pl_author(cls, crossref_author, crossref_author_idx,
                         normalized_pl_authors):
        family = normalize(crossref_author.get('family') or '')
        given = normalize(crossref_author.get('given') or '')

        best_match_score = (0, -math.inf)
        best_match_idx = -1
        for pl_author_idx, pl_author_name in enumerate(
                normalized_pl_authors):
            name_match_score = 0

            if family and family in pl_author_name:
                name_match_score += 2

            if given and given in pl_author_name:
                name_match_score += 1

            index_difference = abs(crossref_author_idx - pl_author_idx)

            if name_match_score:
                match_score = (name_match_score, -index_difference)

                if match_score > best_match_score:
                    best_match_score = match_score
                    best_match_idx = pl_author_idx
        return best_match_idx

    @classmethod
    def _merge_parseland_parse(cls, record, pub):
        if (
                pl_parse := parseland_parse(
                    cls._parseland_api_url(pub))) is not None:
            pl_authors = pl_parse.get('authors', [])
            normalized_pl_authors = [normalize(author.get('raw', '')) for author
                                     in pl_authors]

            for crossref_author_idx, crossref_author in enumerate(
                    record.authors):
                best_match_idx = cls._match_pl_author(crossref_author,
                                                      crossref_author_idx,
                                                      normalized_pl_authors)
                if best_match_idx > -1:
                    pl_author = pl_authors[best_match_idx]
                    crossref_author['is_corresponding'] = pl_author.get('is_corresponding', '')
                    crossref_author['affiliation'] = cls._reconcile_affiliations(
                        crossref_author, pl_author, record.doi)

                record.set_authors(record.authors)

            # In case crossref has no authors and parseland does, use parseland authors
            # Example doi - 10.7717/peerjcs.1261/table-10

            # *** We do not want to do this yet ***

            # if not record.authors and pl_authors:
            #     record.set_authors(pl_authors)

            record.abstract = record.abstract or pl_parse.get('abstract')
            is_oa = bool(pub.response_jsonb.get('oa_locations'))
            if is_oa:
                record.fulltext = record.fulltext or pl_parse.get('readable')

    @classmethod
    def _make_source_specific_record_changes(cls, record, pub):
        cls._merge_parseland_parse(record, pub)

    @classmethod
    def _best_affiliation(cls, aff_ver1, aff_ver2):
        aff_ver1 = cleanup_affiliation(aff_ver1)
        aff_ver2 = cleanup_affiliation(aff_ver2)
        if len(aff_ver1) > len(aff_ver2):
            return aff_ver1
        return aff_ver2

    @classmethod
    def _reconcile_affiliations(cls, crossref_author, pl_author, doi):
        final_affs = []
        pl_affs = pl_author['affiliation'].copy()
        # We probably only want English affiliations from Parseland
        # Sometimes Crossref will have English version and Parseland will have version in another language
        # We probably don't want to keep version that is not in English
        pl_affs = [aff for aff in pl_affs if aff['name'].isascii()] if crossref_author['affiliation'] else pl_affs
        for aff in crossref_author['affiliation']:
            # Assume crossref affiliation is better version initially
            best_aff_version = aff['name']
            pl_aff_idx = cls._match_affiliation(aff['name'], [aff['name'] for aff in pl_affs])
            if pl_aff_idx > -1:
                # If a match is found, pick the better one and set best_aff_version to this one
                pl_aff = pl_affs.pop(pl_aff_idx)
                best_aff_version = pl_aff['name'] if '/nejm' in doi.lower() else cls._best_affiliation(aff['name'], pl_aff['name'])
            final_affs.append({'name': best_aff_version})

        # If there are remaining parseland affiliations, this means that they are not present in crossref. Add them to list of final affs
        final_affs.extend(pl_affs)
        return final_affs
