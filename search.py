from sqlalchemy import sql

from app import db
from pub import Pub


def fulltext_search_title(query, is_oa=None):
    oa_clause = '' if is_oa is None else 'and response_is_oa' if is_oa else 'and not response_is_oa'

    query_statement = sql.text(u'''
      SELECT id, ts_headline('english', title, query), ts_rank_cd(to_tsvector('english', title), query, 32) AS rank
        FROM pub, websearch_to_tsquery('english', :search_str) query  -- or try plainto_tsquery, phraseto_tsquery, to_tsquery
        WHERE to_tsvector('english', title) @@ query
        {oa_clause}
        ORDER BY rank DESC
        LIMIT 75;'''.format(oa_clause=oa_clause))

    rows = db.engine.execute(query_statement.bindparams(search_str=query)).fetchall()
    search_results = {row[0]: {'snippet': row[1], 'score': row[2]} for row in rows}

    responses = [p[0] for p in db.session.query(Pub.response_jsonb).filter(Pub.id.in_(search_results.keys())).all()]

    if is_oa:
        oa_filter = lambda r: r['is_oa']
    elif is_oa is None:
        oa_filter = lambda r: True
    else:
        oa_filter = lambda r: not r['is_oa']

    return [
        {
            'response': response,
            'snippet': search_results[response['doi']]['snippet'],
            'score': search_results[response['doi']]['score'],
        }
        for response in responses if oa_filter(response)
    ][0:50]


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