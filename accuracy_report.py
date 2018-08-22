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
    test_set = db.Column(db.Text)
    no_rg_or_academia = db.Column(db.Boolean)
    genre = db.Column(db.Text)
    since_2017 = db.Column(db.Boolean)
    before_2008 = db.Column(db.Boolean)

    def __init__(self, **kwargs):
        self.id = shortuuid.uuid()[0:20]
        self.created = datetime.datetime.utcnow().isoformat()
        super(AccuracyReport, self).__init__(**kwargs)

    def q_suffix_relevant_set(self):
        q_suffix_parts = []
        if self.test_set:
            q_suffix_parts += ["and input_batch_name='{}'".format(self.test_set)]
        if self.genre:
            q_suffix_parts += ["and pub.response_jsonb->>'genre' = '{}'".format(self.genre)]
        if self.since_2017:
            q_suffix_parts += ["and (pub.response_jsonb->>'year')::int >= 2017"]
        if self.before_2008:
            q_suffix_parts += ["and (pub.response_jsonb->>'year')::int < 2008"]

        return " ".join(q_suffix_parts)

    def set_n(self):
        q = u"""select count(id) from accuracy_from_mturk as accuracy, pub where accuracy.input_id=pub.id and answer_error='{}'"""
        q += self.q_suffix_relevant_set()
        self.n = get_sql_answer(db, q)

    def set_precision(self):
        q = u"""select count(input_id) from accuracy_from_mturk as accuracy, pub where accuracy.input_id=pub.id and response_is_oa and answer_error='{}' and answer_green_box_url != '{}'"""
        if self.no_rg_or_academia:
            q += " and not (answer_green_box_url ilike '%researchgate%' or answer_green_box_url ilike '%academia.edu%')"
        q += self.q_suffix_relevant_set()
        precision_numerator = get_sql_answer(db, q)
        q = u"""select count(input_id) from accuracy_from_mturk as accuracy, pub where accuracy.input_id=pub.id and response_is_oa and answer_error='{}'"""
        q += self.q_suffix_relevant_set()
        precision_denominator = get_sql_answer(db, q)
        try:
            self.precision = float(precision_numerator)/precision_denominator
        except ZeroDivisionError:
            return float('inf')

    def set_recall(self):
        q = u"""select count(input_id) from accuracy_from_mturk as accuracy, pub where accuracy.input_id=pub.id and response_is_oa and answer_error='{}' and answer_green_box_url != '{}'"""
        if self.no_rg_or_academia:
            q += " and not (answer_green_box_url ilike '%researchgate%' or answer_green_box_url ilike '%academia.edu%')"
        q += self.q_suffix_relevant_set()
        recall_numerator = get_sql_answer(db, q)
        q = u"""select count(input_id) from accuracy_from_mturk as accuracy, pub where accuracy.input_id=pub.id and answer_error='{}' and answer_green_box_url != '{}' and answer_error='{}'"""
        if self.no_rg_or_academia:
            q += " and not (answer_green_box_url ilike '%researchgate%' or answer_green_box_url ilike '%academia.edu%')"
        q += self.q_suffix_relevant_set()
        recall_denominator = get_sql_answer(db, q)
        try:
            self.recall = float(recall_numerator)/recall_denominator
        except ZeroDivisionError:
            return float('inf')


    def get_current_precision_errors(self):
        q = u"""select * from accuracy_from_mturk as accuracy, pub where accuracy.input_id=pub.id and response_is_oa and not manual_oa_color like 'open%'"""
        q += self.q_suffix_relevant_set()
        precision_error_pubs = Pub.query.from_statement(text(q)).execution_options(autocommit=True).all()
        return precision_error_pubs

    def get_current_recall_errors(self):
        q = u"""select * from accuracy_from_mturk as accuracy, pub where accuracy.input_id=pub.id and response_is_oa and not manual_oa_color like 'open%'"""
        q += self.q_suffix_relevant_set()
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

    def build_current_report(self, ):
        self.set_n()
        self.set_precision()
        self.set_recall()

    def to_dict(self):
        response = {
            "created": self.created,
            "precision": self.display_precision,
            "recall": self.display_recall,
            "n": self.n,
            "test_set": self.test_set,
            "no_rg_or_academia": self.no_rg_or_academia,
            "genre": self.genre,
            "before_2008": self.before_2008,
            "since_2017": self.since_2017,
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

