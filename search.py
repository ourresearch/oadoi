from sqlalchemy import sql

from app import db
from pub import Pub

def fulltext_search_title(query):
    query_string = """
      SELECT id, ts_headline('english', title, query), ts_rank_cd(to_tsvector('english', title), query, 32) AS rank
        FROM pub_2018, plainto_tsquery('english', '{}') query  -- or try plainto_tsquery, phraseto_tsquery, to_tsquery
        WHERE to_tsvector('english', title) @@ query
        ORDER BY rank DESC
        LIMIT 50;""".format(query)

    rows = db.engine.execute(sql.text(query_string)).fetchall()
    ids = [row[0] for row in rows]
    my_pubs = db.session.query(Pub).filter(Pub.id.in_(ids)).all()
    for row in rows:
        my_id = row[0]
        for my_pub in my_pubs:
            if my_id == my_pub.id:
                my_pub.snippet = row[1]
                my_pub.score = row[2]
    return my_pubs

def autocomplete_phrases(query):
    query_string = ur"""
        with s as (SELECT id, lower(title) as lower_title FROM pub_2018 WHERE title iLIKE '%{query}%')
        select match, count(*) as score from (
            SELECT regexp_matches(lower_title, '({query}\w*?\M)', 'g') as match FROM s
            union all
            SELECT regexp_matches(lower_title, '({query}\w*?(?:\s+\w+){{1}})\M', 'g') as match FROM s
            union all
            SELECT regexp_matches(lower_title, '({query}\w*?(?:\s+\w+){{2}})\M', 'g') as match FROM s
            union all
            SELECT regexp_matches(lower_title, '({query}\w*?(?:\s+\w+){{3}}|)\M', 'g') as match FROM s
        ) s_all
        group by match
        order by score desc, length(match::text) asc
        LIMIT 50;""".format(query=query)

    rows = db.engine.execute(sql.text(query_string)).fetchall()
    phrases = [{"phrase":row[0][0], "score":row[1]} for row in rows if row[0][0]]
    return phrases