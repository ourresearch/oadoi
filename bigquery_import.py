#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Retired 2026-10-15 (oxjob #1685): Unpaywall no longer uses BigQuery, and the Google project's BigQuery API is
disabled on purpose (it cost $1,000-2,000 a month and nothing read the tables).

Heroku Scheduler entries on the oadoi app still call this script (`--table page_new` hourly at :00, `--table
pmh_record` hourly at :30, `--table bq_repo_pulse`, `--clean-page-new`, `--clean-pmh-record` daily). Heroku Scheduler
has no API, so those entries have to be deleted in the dashboard; until then this stub logs one line and exits 0, so
the runs neither call Google nor fail. The old code (Postgres -> BigQuery copies, BigQuery -> Postgres for
bq_repo_pulse / bq_journal_by_licence_by_year) is in git history before this commit.
"""
import sys

if __name__ == "__main__":
    print("BigQuery import retired 2026-10-15, oxjob #1685; nothing to do (args: {})".format(" ".join(sys.argv[1:])))
    sys.exit(0)
