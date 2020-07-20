import argparse
import json
import os
from time import sleep
from urllib import unquote_plus
from urlparse import urlparse, urlunparse

import sendgrid
from sendgrid.helpers.mail.mail import Content
from sendgrid.helpers.mail.mail import Email
from sendgrid.helpers.mail.mail import Mail
from sendgrid.helpers.mail.mail import TrackingSettings, ClickTracking
from sqlalchemy import text

from app import db
from app import logger
from page import PageNew
from pub import Pub


class HybridScrapeTestCase(db.Model):
    id = db.Column(db.Text, primary_key=True)
    scrape_evidence = db.Column(db.Text)
    scrape_license = db.Column(db.Text)
    scrape_metadata_url = db.Column(db.Text)
    scrape_pdf_url = db.Column(db.Text)


def _hybrid_to_dict(pub_or_test_case):
    return {
        'scrape_evidence': pub_or_test_case.scrape_evidence,
        'scrape_license': pub_or_test_case.scrape_license,
        'scrape_metadata_url': pub_or_test_case.scrape_metadata_url,
        'scrape_pdf_url': pub_or_test_case.scrape_pdf_url,
    }


class GreenScrapeTestCase(db.Model):
    id = db.Column(db.Text, primary_key=True)
    scrape_version = db.Column(db.Text)
    scrape_license = db.Column(db.Text)
    scrape_metadata_url = db.Column(db.Text)
    scrape_pdf_url = db.Column(db.Text)


def _green_to_dict(page_or_test_case):
    return {
        'scrape_version': page_or_test_case.scrape_version,
        'scrape_license': page_or_test_case.scrape_license,
        'scrape_metadata_url': page_or_test_case.scrape_metadata_url,
        'scrape_pdf_url': page_or_test_case.scrape_pdf_url,
    }


def _normalize_url(url):
    if not url:
        return url

    parts = urlparse(url)
    parts = parts._replace(path=unquote_plus(parts.path))
    return urlunparse(parts)


def _run_hybrid_tests():
    test_cases = HybridScrapeTestCase.query.all()
    test_ids = [tc.id for tc in test_cases]

    # refresh test cases now

    refresh_query = text(u'''
        update pub_refresh_queue
        set priority=1000000, finished = null
        where id = any(:ids)
        and started is null
    '''.format()).bindparams(ids=test_ids)


    # prevent update from recalculating priority now

    update_query = text(u'''
        update pub_queue
        set finished=now()
        where id = any(:ids)
        and started is null
    '''.format()).bindparams(ids=test_ids)

    db.session.execute(refresh_query)
    db.session.execute(update_query)
    db.session.commit()

    # wait for refresh to finish

    status_query = text(u'''
        select
            count(*) as total,
            sum(case when finished is not null then 1 else 0 end) as done
        from pub_refresh_queue
        where id = any(:ids)
    '''.format()).bindparams(ids=test_ids)

    while True:
        total, done = db.engine.execute(status_query).first()

        if total == done:
            break

        logger.info(u'waiting for hybrid scrape: {}/{}'.format(done, total))
        sleep(30)

    pubs = Pub.query.filter(Pub.id.in_(test_ids)).all()
    pubs_by_id = dict((p.id, p) for p in pubs)

    successes = {}
    failures = {}

    for test_case in test_cases:
        this_pub = pubs_by_id[test_case.id]

        if (
            test_case.scrape_evidence == this_pub.scrape_evidence and
            test_case.scrape_license == this_pub.scrape_license and
            _normalize_url(test_case.scrape_pdf_url) == _normalize_url(this_pub.scrape_pdf_url) and
            _normalize_url(test_case.scrape_metadata_url) == _normalize_url(this_pub.scrape_metadata_url)
        ):
            successes[test_case.id] = _hybrid_to_dict(test_case)
        else:
            failures[test_case.id] = {
                'expected': _hybrid_to_dict(test_case),
                'got': _hybrid_to_dict(this_pub)
            }

    report = u'failed:\n\n{}\n\npassed:\n\n{}\n'.format(json.dumps(failures, indent=4), json.dumps(successes, indent=4))

    return report


def _run_green_tests():
    test_cases = GreenScrapeTestCase.query.all()
    test_ids = [tc.id for tc in test_cases]

    # refresh test cases now

    pages = PageNew.query.filter(PageNew.id.in_(test_ids)).all()
    for i, p in enumerate(pages):
        logger.info('refreshing page {} {}/{}'.format(p.id, i, len(pages)))
        p.scrape()

    db.session.commit()

    pages_by_id = dict((p.id, p) for p in pages)

    successes = {}
    failures = {}

    for test_case in test_cases:
        this_page = pages_by_id.get(test_case.id, None)

        if this_page is None:
            failures[test_case.id] = {
                'expected': _green_to_dict(test_case),
                'got': None
            }
        elif (
            test_case.scrape_version == this_page.scrape_version and
            test_case.scrape_license == this_page.scrape_license and
            _normalize_url(test_case.scrape_pdf_url) == _normalize_url(this_page.scrape_pdf_url) and
            _normalize_url(test_case.scrape_metadata_url) == _normalize_url(this_page.scrape_metadata_url)
        ):
            successes[test_case.id] = _green_to_dict(test_case)
        else:
            failures[test_case.id] = {
                'expected': _green_to_dict(test_case),
                'got': _green_to_dict(this_page)
            }

    report = u'failed:\n\n{}\n\npassed:\n\n{}\n'.format(json.dumps(failures, indent=4), json.dumps(successes, indent=4))

    return report


def _send_report(subject, report, to_address):
    content = Content("text/plain", report)
    from_email = Email("dev@ourresearch.org", "Unpaywall Team")
    to_email = Email(to_address)
    email = Mail(from_email, subject, to_email, content)

    tracking_settings = TrackingSettings()
    tracking_settings.click_tracking = ClickTracking(False, False)
    email.tracking_settings = tracking_settings

    sg = sendgrid.SendGridAPIClient(apikey=os.environ.get('SENDGRID_API_KEY'))
    sg.client.mail.send.post(request_body=email.get())

    logger.info(u'sent "{}" report to {}'.format(subject, to_address))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the hybrid scrape regression tests.")
    parser.add_argument('--email', nargs="?", type=str, help="where to send the report (optional)")
    parser.add_argument('--hybrid', default=False, action='store_true', help="run the hybrid tests")
    parser.add_argument('--green', default=False, action='store_true', help="run the green tests")

    parsed_args = parser.parse_args()

    if parsed_args.hybrid:
        hybrid_report = _run_hybrid_tests()
        print hybrid_report

        if parsed_args.email:
            _send_report(u'hybrid scrape regression test results', hybrid_report, parsed_args.email)

    if parsed_args.green:
        green_report = _run_green_tests()
        print green_report

        if parsed_args.email:
            _send_report(u'green scrape regression test results', green_report, parsed_args.email)
