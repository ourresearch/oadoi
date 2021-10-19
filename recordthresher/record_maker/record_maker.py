from abc import ABC, abstractmethod

from app import logger


class RecordMaker(ABC):
    @staticmethod
    @abstractmethod
    def _is_specialized_record_maker(**kwargs):
        pass

    @classmethod
    @abstractmethod
    def make_record(cls, **kwargs):
        pass

    @classmethod
    @abstractmethod
    def _make_record_impl(cls, **kwargs):
        pass

    @classmethod
    def _dispatch(cls, **kwargs):
        for subcls in cls.__subclasses__():
            if subcls._is_specialized_record_maker(**kwargs):
                logger.info(f'making record with {subcls}')
                return subcls._make_record_impl(**kwargs)

        logger.info(f'making record with base {cls}')
        return cls._make_record_impl(**kwargs)
