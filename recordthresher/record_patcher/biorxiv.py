from .patcher import CrossrefDoiPatcher


class BiorxivPatcher(CrossrefDoiPatcher):
    @classmethod
    def _should_patch_record(cls, record, pub):
        return pub.doi.startswith('10.1101/') and pub.genre == 'posted-content'

    @classmethod
    def _patch_record(cls, record, pub):
        if (pl_authors := cls._parseland_authors(pub)) is not None:
            record.authors = pl_authors
