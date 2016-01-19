from app import db


def add_profile(**kwargs):
    my_profile = Profile(**kwargs)
    db.session.merge(my_profile)
    db.session.commit()  
    return my_profile


class Profile(db.Model):
    id = db.Column(db.Text, primary_key=True)
    given_names = db.Column(db.Text)
    family_name = db.Column(db.Text)
    api_raw = db.Column(db.Text)

    def __repr__(self):
        return u'<Profile ({id}) "{given_names} {family_name}" >'.format(
            id=self.id,
            given_names=self.given_names, 
            family_name=self.family_name
        )




