from abc import ABC, abstractmethod
from time import sleep

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

    @classmethod
    def _parseland_authors_for_url(cls, parseland_url):
        retry = True
        next_retry_interval = 1
        cumulative_wait = 0
        max_cumulative_wait = 10

        while retry and cumulative_wait < max_cumulative_wait:
            parseland_response = requests.get(parseland_url)

            if parseland_response.ok:
                logger.info('got a 200 response from parseland')
                try:
                    parseland_json = parseland_response.json()
                    message = parseland_json.get('message', None)

                    if not isinstance(message, list):
                        logger.error("message isn't a list")
                        return None

                    authors = []
                    logger.error(f'got {len(message)} authors')

                    for pl_author in message:
                        author = {'raw': pl_author.get('name'), 'affiliation': []}
                        pl_affiliations = pl_author.get('affiliations')

                        if isinstance(pl_affiliations, list):
                            for pl_affiliation in pl_affiliations:
                                author['affiliation'].append({'name': pl_affiliation})

                        authors.append(normalize_author(author))

                    return authors
                except ValueError as e:
                    logger.error("response isn't valid json")
                    return None
            else:
                logger.warning(f'got error response from parseland: {parseland_response}')

                if parseland_response.status_code == 404 and 'Source file not found' in parseland_response.text:
                    logger.info(f'retrying in {next_retry_interval} seconds')
                    sleep(next_retry_interval)
                    cumulative_wait += next_retry_interval
                    next_retry_interval *= 1.5
                else:
                    logger.info('not retrying')
                    retry = False

        logger.info(f'done retrying after {cumulative_wait} seconds')
        return None


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
        return cls._parseland_authors_for_url(
            f'https://parseland.herokuapp.com/parse-repository?page-id={repo_page.id}'
        )


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

    @classmethod
    def _parseland_authors(cls, pub):
        return cls._parseland_authors_for_url(
            f'https://parseland.herokuapp.com/parse-publisher?doi={pub.id}'
        )
