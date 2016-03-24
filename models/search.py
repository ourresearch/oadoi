from sqlalchemy import sql

from app import db

def autocomplete(search_str):

    command = """(select first_name || ' ' || family_name as full_name, altmetric_score, orcid_id, id, 1 as sort_order
    from person
    where (first_name || ' ' || family_name) ilike '{str}%'
    order by altmetric_score desc
    limit 10)
    union
    (select first_name || ' ' || family_name as full_name, altmetric_score, orcid_id, id, 2 as sort_order
    from person
    where family_name ilike '{str}%'
    order by altmetric_score desc
    limit 10)
    order by sort_order, altmetric_score desc
    """.format(str=search_str)

    res = db.session.connection().execute(sql.text(command))
    rows = res.fetchall()
    ret = []
    prev_type = "there is no current type"


    for row in rows:
        ret.append({
            "name": row[0],
            "altmetric_score": row[1],
            "orcid_id": row[2],
            "id": row[3]
        })

    return ret










