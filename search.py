from sqlalchemy import sql

from app import db
from pub import Pub


def fulltext_search_title(query, is_oa=None, page=1):
    oa_clause = 'true' if is_oa is None else 'response_is_oa' if is_oa else 'not response_is_oa'

    query_statement = sql.text(u'''
        with matches as materialized (
            select id, title, query, response_is_oa
            from pub, websearch_to_tsquery('english', :search_str) query
            where to_tsvector('english', title) @@ query
            limit 1000
        )
        select
            id,
            ts_headline('english', title, query),
            ts_rank_cd(to_tsvector('english', title), query, 1) as rank
        from matches
        where {oa_clause}
        order by rank desc limit 50 offset {offset}
        ;'''.format(oa_clause=oa_clause, offset=int(page-1)*50))

    rows = db.engine.execute(query_statement.bindparams(search_str=query)).fetchall()
    search_results = {row[0]: {'snippet': row[1], 'score': row[2]} for row in rows}

    cached_responses = [p[0] for p in db.session.query(Pub.response_jsonb).filter(Pub.id.in_(search_results.keys())).all()]

    if is_oa:
        oa_filter = lambda r: r['is_oa']
    elif is_oa is None:
        oa_filter = lambda r: True
    else:
        oa_filter = lambda r: not r['is_oa']

    filtered_responses = [
        {
            'response': response,
            'snippet': search_results[response['doi']]['snippet'],
            'score': search_results[response['doi']]['score'],
        }
        for response in cached_responses if oa_filter(response)
    ][0:50]

    return sorted(filtered_responses, key=lambda r: r['score'], reverse=True)

def autocomplete_phrases(query):
    query_statement = sql.text(ur"""
        with s as (SELECT id, lower(title) as lower_title FROM pub_2018 WHERE title iLIKE :p0)
        select match, count(*) as score from (
            SELECT regexp_matches(lower_title, :p1, 'g') as match FROM s
            union all
            SELECT regexp_matches(lower_title, :p2, 'g') as match FROM s
            union all
            SELECT regexp_matches(lower_title, :p3, 'g') as match FROM s
            union all
            SELECT regexp_matches(lower_title, :p4, 'g') as match FROM s
        ) s_all
        group by match
        order by score desc, length(match::text) asc
        LIMIT 50;""").bindparams(
            p0='%{}%'.format(query),
            p1=ur'({}\w*?\M)'.format(query),
            p2=ur'({}\w*?(?:\s+\w+){{1}})\M'.format(query),
            p3=ur'({}\w*?(?:\s+\w+){{2}})\M'.format(query),
            p4=ur'({}\w*?(?:\s+\w+){{3}}|)\M'.format(query)
        )

    rows = db.engine.execute(query_statement).fetchall()
    phrases = [{"phrase":row[0][0], "score":row[1]} for row in rows if row[0][0]]
    return phrases