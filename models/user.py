from sqlalchemy.dialects.postgresql import JSONB

from app import db





class User(db.Model):
    screen_name = db.Column(db.Text, primary_key=True)
    name = db.Column(db.Text)
    profile_image_url = db.Column(db.Text)
    description = db.Column(db.Text)
    api_raw = db.Column(JSONB)

    def to_dict(self):
        return {
            "screen_name": self.screen_name,
            "name": self.name,
            "profile_image_url": self.profile_image_url,
            "description": self.description
        }


