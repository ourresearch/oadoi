from collections import defaultdict

import requests
import csv

from recordthresher.record import Record
from sqlalchemy import desc, asc


def run_stats():
    total = 10000
    yield_per = 1000
    total_processed = 0
    all_false = 0
    all_null = 0
    some_true = 0
    publisher = {}
    reason = defaultdict(list)
    publisher_true = defaultdict(int)
    publisher_null = defaultdict(int)
    publisher_total = defaultdict(int)
    for r in Record.query.with_entities(Record.authors, Record.updated, Record.doi, Record.publisher).order_by(desc(Record.updated)).limit(total).yield_per(yield_per):
        values = [str(author["is_corresponding"]) for author in r.authors if "is_corresponding" in author]
        if r.publisher == "Springer Science and Business Media LLC" and not values:
            print(r.doi)
        if not publisher_total.get(r.publisher):
            publisher_total[r.publisher] = 1
        else:
            publisher_total[r.publisher] = publisher_total[r.publisher] + 1
        if values:
            total_processed = total_processed + 1
        # else:
        #     try:
        #         res = requests.get(f"https://parseland.herokuapp.com/parse-publisher?doi={r.doi}")
        #         json_response = res.json()
        #         if json_response:
        #             if "message" in json_response and "authors" in json_response["message"] and len(json_response["message"]["authors"]) == 0:
        #                 reason["no authors"].append(f"{r.doi} ({r.publisher})")
        #             elif "message" in json_response and "authors" in json_response["message"] and len(json_response["message"]["authors"]) > 0:
        #                 reason["authors found but not in database"].append(f"{r.doi} ({r.publisher})")
        #             elif "error" in json_response and "Source file not" in json_response["error"]:
        #                 reason["no source file"].append(f"{r.doi} ({r.publisher})")
        #             elif "error" in json_response and "Parser not found" in json_response["error"]:
        #                 reason["no parser"].append(f"{r.doi} ({r.publisher})")
        #     except:
        #         pass
        if "True" in values:
            if not publisher_true.get(r.publisher):
                publisher_true[r.publisher] = 1
            else:
                publisher_true[r.publisher] = publisher_true[r.publisher] + 1
            some_true = some_true + 1
            if not publisher.get(r.publisher):
                publisher[r.publisher] = 1
            else:
                publisher[r.publisher] = publisher[r.publisher] + 1
        elif "False" in values:
            all_false = all_false + 1
        elif "None" in values:
            if not publisher_null.get(r.publisher):
                publisher_null[r.publisher] = 1
            else:
                publisher_null[r.publisher] = publisher_null[r.publisher] + 1
            all_null = all_null + 1

    # no_authors_count = len(reason["no authors"])
    # no_source_count = len(reason["no source file"])
    # no_parser_count = len(reason["no parser"])
    # authors_not_in_db = len(reason["authors found but not in database"])


    # print(f"No authors: {no_authors_count}, no source file: {no_source_count}, no parser: {no_parser_count}, authors not in db: {authors_not_in_db}")
    print(f"some true count: {some_true}")
    # print(f"percentage true out of processed: {some_true / total_processed}")
    # print(f"percentage true out of total: {some_true / total}")
    # print(f"all false: {all_false}, ({all_false/(some_true + all_false)})",)
    print(f"null: {all_null}")
    print(f"total records processed: {total_processed}")
    print(f"total records not processed: {total - total_processed}")
    save_publisher_stats(publisher_true, publisher_null, publisher_total)
    # print(f"percentage processed: {total_processed / total}")


def save_publisher_stats(publisher_true, publisher_null, publisher_total):
    with open('publisher_true.csv', 'w') as csv_file:
        writer = csv.writer(csv_file)
        for key, value in publisher_true.items():
            writer.writerow([key, value])

    with open('publisher_null.csv', 'w') as csv_file:
        writer = csv.writer(csv_file)
        for key, value in publisher_null.items():
            writer.writerow([key, value])

    with open('publisher_total.csv', 'w') as csv_file:
        writer = csv.writer(csv_file)
        for key, value in publisher_total.items():
            writer.writerow([key, value])


if __name__ == "__main__":
    run_stats()
