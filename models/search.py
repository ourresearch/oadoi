from sqlalchemy import sql

from app import db

def autocomplete(search_str):

    command = """(select first_name || ' ' || family_name as full_name, num_posts, orcid_id, id, 1 as sort_order
    from person
    where (first_name || ' ' || family_name) ilike '{str}%'
    order by num_posts desc
    limit 10)
    union
    (select first_name || ' ' || family_name as full_name, num_posts, orcid_id, id, 2 as sort_order
    from person
    where family_name ilike '{str}%'
    order by num_posts desc
    limit 10)
    order by sort_order, num_posts desc
    """.format(str=search_str)

    res = db.session.connection().execute(sql.text(command))
    rows = res.fetchall()
    ret = []
    prev_type = "there is no current type"


    for row in rows:
        ret.append({
            "name": row[0],
            "num_posts": row[1],
            "orcid_id": row[2],
            "id": row[3]
        })

    return ret










