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
    num_distinct_pmh_records = db.Column(db.Text)
    num_distinct_pmh_records_matching_dois = db.Column(db.Text)
    num_distinct_pmh_records_matching_dois_with_fulltext = db.Column(db.Text)
    num_distinct_pmh_submitted_version = db.Column(db.Text)
    num_distinct_pmh_accepted_version = db.Column(db.Text)
    num_distinct_pmh_published_version = db.Column(db.Text)
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
            "num_pmh_records": self.num_distinct_pmh_records,
            "last_harvest": self.last_harvested,
            "num_pmh_records_matching_dois": self.num_distinct_pmh_records_matching_dois,
            "num_pmh_records_matching_dois_with_fulltext": self.num_distinct_pmh_records_matching_dois_with_fulltext
        }
        results["by_version_distinct_pmh_records_matching_dois"] = {
            "submittedVersion": self.num_distinct_pmh_submitted_version,
            "acceptedVersion": self.num_distinct_pmh_accepted_version,
            "publishedVersion": self.num_distinct_pmh_published_version
        }

        return results
