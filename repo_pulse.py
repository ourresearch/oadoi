from app import db


class BqRepoPulse(db.Model):
    endpoint_id = db.Column(db.Text, primary_key=True)
    collected = db.Column(db.DateTime)
    repository_name = db.Column(db.Text)
    institution_name = db.Column(db.Text)
    pmh_url = db.Column(db.Text)
    check0_identify_status = db.Column(db.Text)
    check1_query_status = db.Column(db.Text)
    last_harvested = db.Column(db.DateTime)
    num_distinct_pmh_records = db.Column(db.Numeric)
    num_distinct_pmh_records_matching_dois = db.Column(db.Numeric)
    num_distinct_pmh_records_matching_dois_with_fulltext = db.Column(db.Numeric)
    num_distinct_pmh_submitted_version = db.Column(db.Numeric)
    num_distinct_pmh_accepted_version = db.Column(db.Numeric)
    num_distinct_pmh_published_version = db.Column(db.Numeric)
    error = db.Column(db.Text)

    def __repr__(self):
        return "<BqRepoPulse ({})>".format(self.endpoint_id)


    def to_dict(self):
        results = {}

        results["metadata"] = {
            "endpoint_id": self.endpoint_id,
            "repository_name": self.repository_name,
            "institution_name": self.institution_name,
            "pmh_url": self.pmh_url
        }
        results["status"] = {
            "check0_identify_status": self.check0_identify_status,
            "check1_query_status": self.check1_query_status,
            "num_pmh_records": int(self.num_distinct_pmh_records or 0),
            "last_harvest": self.last_harvested,
            "num_pmh_records_matching_dois": int(self.num_distinct_pmh_records_matching_dois or 0),
            "num_pmh_records_matching_dois_with_fulltext": int(self.num_distinct_pmh_records_matching_dois_with_fulltext or 0)
        }
        results["by_version_distinct_pmh_records_matching_dois"] = {
            "submittedVersion": int(self.num_distinct_pmh_submitted_version or 0),
            "acceptedVersion": int(self.num_distinct_pmh_accepted_version or 0),
            "publishedVersion": int(self.num_distinct_pmh_published_version or 0)
        }

        return results
