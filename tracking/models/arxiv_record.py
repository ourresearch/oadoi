from datetime import datetime
from app import db

class ArxivTrack(db.Model):
    __table_args__ = {"schema": "tracking"}
    __tablename__ = "arxiv_record"

    id = db.Column(db.BigInteger, primary_key=True)
    arxiv_id = db.Column(db.Text)
    created_at = db.Column(db.DateTime)
    first_tracked_at = db.Column(db.DateTime)
    last_tracked_at = db.Column(db.DateTime)
    pmh_record_id = db.Column(db.Text)
    pmh_record_found = db.Column(db.DateTime)
    page_new_id = db.Column(db.Text)
    page_new_found = db.Column(db.DateTime)
    recordthresher_record_id = db.Column(db.Text)
    recordthresher_record_found = db.Column(db.DateTime)
    green_scrape_queue_finished = db.Column(db.DateTime)
    green_scrape_queue_found = db.Column(db.DateTime)
    active = db.Column(db.Boolean)
    note = db.Column(db.Text)

    def track(self):
        from ..trackdb import (
            query_pmh_record_by_arxiv_id,
            query_page_new_by_arxiv_id,
            query_green_scrape_queue_by_page_new_id,
        )

        now = datetime.utcnow().isoformat()
        if not self.first_tracked_at:
            self.first_tracked_at = now
        
        # pmh_record table
        if not self.pmh_record_found:
            results = query_pmh_record_by_arxiv_id(self.arxiv_id)
            if len(results):
                self.pmh_record_found = now
                self.pmh_record_id = results[0].id

        # page_new table
        if not self.page_new_found:
            results = query_page_new_by_arxiv_id(self.arxiv_id)
            if len(results):
                self.page_new_found = now
                self.page_new_id = results[0].id

        # page_green_scrape_queue table
        if self.page_new_id is not None:
            results = query_green_scrape_queue_by_page_new_id(self.page_new_id)
            if len(results):
                if not self.green_scrape_queue_found:
                    self.green_scrape_queue_found = now
                if self.green_scrape_queue_finished is None and results[0].finished is not None:
                    self.green_scrape_queue_finished = results[0].finished
        
        self.last_tracked_at = now
        db.session.commit()