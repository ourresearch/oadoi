import os
import datetime
import requests
from time import sleep
from time import time
import re
import json
import shortuuid
import argparse
from sqlalchemy import text

from app import db
from app import logger
from util import elapsed
from util import safe_commit
from util import get_sql_answer
from pub import Pub


class AccuracyReport(db.Model):
    id = db.Column(db.Text, primary_key=True)
    created = db.Column(db.DateTime)
    precision = db.Column(db.Numeric)
    recall = db.Column(db.Numeric)
    n = db.Column(db.Numeric)
    run_set = db.Column(db.Text)

    def __init__(self, **kwargs):
        self.id = shortuuid.uuid()[0:20]
        self.created = datetime.datetime.utcnow().isoformat()
        super(AccuracyReport, self).__init__(**kwargs)

    def set_run_set(self):
        self.run_set = "test and training"

    def set_n(self):
        q = u"""select count(doi) from accuracy, pub where accuracy.doi=pub.id"""
        self.n = get_sql_answer(db, q)

    def set_precision(self):
        q = u"""select count(*) from accuracy, pub where accuracy.doi=pub.id and response_is_oa and manual_oa_color like 'open%'"""
        precision_numerator = get_sql_answer(db, q)
        q = u"""select count(*) from accuracy, pub where accuracy.doi=pub.id and response_is_oa"""
        precision_denominator = get_sql_answer(db, q)
        self.precision = float(precision_numerator)/precision_denominator

    def set_recall(self):
        q = u"""select count(*) from accuracy, pub where accuracy.doi=pub.id and response_is_oa and manual_oa_color like 'open%'"""
        recall_numerator = get_sql_answer(db, q)
        q = u"""select count(*) from accuracy where manual_oa_color like 'open%'"""
        recall_denominator = get_sql_answer(db, q)
        self.recall = float(recall_numerator)/recall_denominator

    def get_current_precision_errors(self):
        q = u"""select * from accuracy, pub where accuracy.doi=pub.id and response_is_oa and not manual_oa_color like 'open%'"""
        precision_error_pubs = Pub.query.from_statement(text(q)).execution_options(autocommit=True).all()
        return precision_error_pubs

    def get_current_recall_errors(self):
        q = u"""select * from accuracy, pub where accuracy.doi=pub.id and response_is_oa and not manual_oa_color like 'open%'"""
        recall_error_pubs = Pub.query.from_statement(text(q)).execution_options(autocommit=True).all()
        return recall_error_pubs

    @property
    def display_precision(self):
        if not self.precision:
            return self.precision
        return u"{}%".format(round(self.precision*100, 1))

    @property
    def display_recall(self):
        if not self.recall:
            return self.recall
        return u"{}%".format(round(self.recall*100, 1))

    def build_current_report(self):
        self.set_n()
        self.set_run_set()
        self.set_precision()
        self.set_recall()

    def to_dict(self):
        response = {
            "created": self.created,
            "precision": self.display_precision,
            "recall": self.display_recall,
            "n": self.n,
            "run_set": self.run_set,
        }
        return response

    def __repr__(self):
        return u"<AccuracyReport ( {} ) {} {}>".format(self.id, self.display_precision, self.display_precision)



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run stuff.")

    function = get_new_dois_and_data_from_crossref

    parser.add_argument('--first', nargs="?", type=str, help="first filename to process (example: --first 2006-01-01)")
    parser.add_argument('--last', nargs="?", type=str, help="last filename to process (example: --last 2006-01-01)")

    parser.add_argument('--query_doi', nargs="?", type=str, help="pull in one doi")

    parser.add_argument('--today', action="store_true", default=False, help="use if you want to pull in crossref records from last 2 days")
    parser.add_argument('--week', action="store_true", default=False, help="use if you want to pull in crossref records from last 7 days")

    parser.add_argument('--chunk_size', nargs="?", type=int, default=1000, help="how many docs to put in each POST request")


    parsed = parser.parse_args()

    logger.info(u"calling {} with these args: {}".format(function.__name__, vars(parsed)))
    function(**vars(parsed))

