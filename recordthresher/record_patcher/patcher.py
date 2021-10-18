from abc import ABC, abstractmethod

import requests
from lxml import etree

from app import logger
from recordthresher.util import normalize_author


class RecordPatcher(ABC):
    @classmethod
    @abstractmethod
    def _should_patch_record(cls, **kwargs):
        pass

    @classmethod
    @abstractmethod
    def _patch_record(cls, **kwargs):
        pass

    @classmethod
    def _apply_right_patcher(cls, **kwargs):
        for subcls in cls.__subclasses__():
            if subcls._should_patch_record(**kwargs):
                logger.info(f'patching record with {subcls}')
                subcls._patch_record(**kwargs)
                break

    @classmethod
    @abstractmethod
    def patch_record(cls, **kwargs):
        pass


class PmhRecordPatcher(RecordPatcher):
    @classmethod
    @abstractmethod
    def _should_patch_record(cls, record, pmh_record, repo_page):
        pass

    @classmethod
    @abstractmethod
    def _patch_record(cls, record, pmh_record, repo_page):
        pass

    @classmethod
    def patch_record(cls, record, pmh_record, repo_page):
        cls._apply_right_patcher(record=record, pmh_record=pmh_record, repo_page=repo_page)

    @classmethod
    def _xml_tree(cls, xml, clean_namespaces=True):
        if not xml:
            return None

        try:
            tree = etree.fromstring(xml)

            if clean_namespaces:
                for e in tree.getiterator():
                    e.tag = etree.QName(e).localname

                etree.cleanup_namespaces(tree)

            return tree
        except etree.ParseError as e:
            logger.exception(f'etree parse error: {e}')
            return None

    @classmethod
    def _parseland_authors(cls, repo_page):
        parseland_response = requests.get(f'https://parseland.herokuapp.com/parse-repository?page-id={repo_page.id}')

        if parseland_response.ok:
            try:
                parseland_json = parseland_response.json()
                message = parseland_json.get('message', None)

                if not isinstance(message, list):
                    return None

                authors = []

                for pl_author in message:
                    author = {'raw': pl_author.get('name'), 'affiliation': []}
                    pl_affiliations = pl_author.get('affiliations')

                    if isinstance(pl_affiliations, list):
                        for pl_affiliation in pl_affiliations:
                            author['affiliation'].append({'name': pl_affiliation})

                    authors.append(normalize_author(author))

                return authors
            except ValueError as e:
                return None

        return None


class CrossrefDoiPatcher(RecordPatcher):
    @classmethod
    @abstractmethod
    def _should_patch_record(cls, record, pub):
        pass

    @classmethod
    @abstractmethod
    def _patch_record(cls, record, pub):
        pass

    @classmethod
    def patch_record(cls, record, pub):
        cls._apply_right_patcher(record=record, pub=pub)
