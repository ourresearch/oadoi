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

