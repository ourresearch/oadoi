from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import sql

from app import db
from models.package import make_language

# run create_tags_table.sql to automatically create this table 
#  from the tags column in the package table

class Tags(db.Model):
    id = db.Column(db.Text, primary_key=True)
    unique_tag = db.Column(db.Text)
    namespace = db.Column(db.Text)
    count = db.Column(db.Integer)
    count_academic = db.Column(db.Integer)

    def __repr__(self):
        return u'<Tag "{}">'.format(self.id)


    @property
    def related_tags(self):
        number_tags_to_return = 5

        command = """select tag2, c 
                        from cooccurring_tags 
                        where tag1='{my_tag}' 
                        order by c desc
                        limit {limit}""".format(
                            my_tag = self.unique_tag, 
                            limit = number_tags_to_return
                            )
        query = db.session.connection().execute(sql.text(command))
        rows = query.fetchall()
        ret = []
        for row in rows:
            ret.append({"name":row[0], "count":row[1]})
        return ret


    @property
    def as_snippet(self):

        ret = {
        	"language": make_language(self.namespace),
        	"count": self.count,
            "count_academic": self.count_academic,
        	"name": self.unique_tag,
            "related_tags": self.related_tags
        }

        return ret