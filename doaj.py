from sqlalchemy import text

from app import db

_doaj_issns = []


def doaj_issns():
    global _doaj_issns
    if not _doaj_issns:
        # remove hyphens here so don't have to do it every time

        doaj_issns_with_hyphens = db.engine.execute(
            text("""
                select issn, license, year from filtered_doaj_journals where issn is not null
                union all
                select e_issn as issn, license, year from filtered_doaj_journals where e_issn is not null
            """)
        ).fetchall()

        for row in doaj_issns_with_hyphens:
            (row_issn_with_hyphen, row_license, doaj_start_year) = row
            row_issn_no_hypen = row_issn_with_hyphen.replace("-", "")
            _doaj_issns.append([row_issn_no_hypen, row_license, doaj_start_year])
    return _doaj_issns


_doaj_titles = []


def doaj_titles():
    global _doaj_titles
    if not _doaj_titles:
        _doaj_titles = [
            (title.encode("utf-8"), license, start_year) for (title, license, start_year) in
            db.engine.execute(
               text("""
                    select title, license, year from filtered_doaj_journals where title is not null
                    union all
                    select alt_title as title, license, year from filtered_doaj_journals where alt_title is not null
                """)
            ).fetchall()
        ]
    return _doaj_titles
