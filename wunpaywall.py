import json

from app import db


class WunpaywallPub(db.Model):
    __tablename__ = 'unpaywall_from_walden_without_doi'
    __table_args__ = {'schema': 'unpaywall'}
    __bind_key__ = 'openalex'

    doi = db.Column(db.String, primary_key=True)
    json_response = db.Column(db.Text)

    def to_dict(self):
        response = json.loads(self.json_response)
        return response


class WunpaywallFeed(db.Model):
    __tablename__ = 'export_metadata'
    __table_args__ = {'schema': 'unpaywall'}
    __bind_key__ = 'openalex'

    export_timestamp = db.Column(db.String(255), primary_key=True)
    mode = db.Column(db.String(50), primary_key=True)
    file_name = db.Column(db.String(255), primary_key=True)

    file_path = db.Column(db.String(500))
    file_size_bytes = db.Column(db.BigInteger)
    line_count = db.Column(db.Integer)
    from_date = db.Column(db.Date)
    to_date = db.Column(db.Date)

    @staticmethod
    def get_feed_list(api_key="YOUR_API_KEY", mode="daily", limit=30):
        query = WunpaywallFeed.query.filter_by(mode=mode).order_by(
            WunpaywallFeed.export_timestamp.desc()
        )

        if limit:
            query = query.limit(limit)

        records = query.all()
        feed_items = []

        for record in records:
            date_parts = record.export_timestamp.split('T')
            date_part = date_parts[0] if len(date_parts) > 0 else None

            # create API URL with the provided API key
            base_url = "https://api.unpaywall.org/daily-feed/changefile/"
            url = f"{base_url}{record.file_name}?api_key={api_key}"

            feed_items.append({
                "filename": record.file_name,
                "size": record.file_size_bytes,
                "filetype": 'jsonl',
                "url": url,
                "last_modified": record.export_timestamp,
                "lines": record.line_count,
                "date": date_part
            })

        return feed_items

    def __repr__(self):
        """String representation of the model instance"""
        return f"<WunpaywallMetaData {self.mode} {self.file_name} {self.export_timestamp}>"
