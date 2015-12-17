from sqlalchemy import sql
from package import prep_summary

from app import db

def autocomplete(search_str):

    command = """(select project_name, impact, api_raw->'info'->>'summary' as summary, 'pypi_project' as type, 1 as first_sort, id
    from package
    where host='pypi'
    and project_name ilike '{str}%'
    order by impact desc
    limit 3)
    union
    (select project_name, impact, api_raw->>'Title' as summary, 'cran_project' as type, 2 as first_sort, id
    from package
    where host='cran'
    and project_name ilike '{str}%'
    order by impact desc
    limit 3)
    union
    (select name, impact, github_about->>'company' as summary, 'person' as type, 3 as first_sort, id::text as id
    from person
    where name ilike '{str}%'
    or name ilike '% {str}%'
    order by impact desc
    limit 3)
    union
    (select unique_tag, "count_academic" as impact, namespace as summary, 'tag' as type, 4 as first_sort, id
    from tags
    where unique_tag ilike '{str}%'
    or unique_tag ilike '% {str}%'
    or unique_tag ilike '/{str}%'
    order by "count_academic" desc
    limit 3)
    order by first_sort, impact desc""".format(str=search_str)

    res = db.session.connection().execute(sql.text(command))
    rows = res.fetchall()
    ret = []
    prev_type = "there is no current type"


    for row in rows:
        ret.append({
            "name": row[0],
            "impact": row[1],
            "summary": prep_summary(row[2]),
            "type": row[3],
            "is_first": prev_type != row[3],
            # row[4] is first_sort param, ignore it.
            "id": row[5]
        })
        prev_type = row[3]


    return ret

   








