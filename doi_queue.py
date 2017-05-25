import os
import argparse
from time import time
from time import sleep
from sqlalchemy import sql
from sqlalchemy import exc
from subprocess import call
import heroku3
import boto.ec2
from boto.manage.cmdshell import sshclient_from_instance


from app import db
from jobs import update_registry
import jobs_defs # needs to be imported so the definitions get loaded into the registry
from util import elapsed
from util import run_sql
from util import get_sql_answer


def monitor_till_done(do_hybrid=False):
    while number_waiting_on_queue(do_hybrid) > 0:
        print_status(do_hybrid)
        sleep(2)

def number_total_on_queue(do_hybrid):
    num = get_sql_answer(db, "select count(id) from doi_queue")
    return num

def number_waiting_on_queue(do_hybrid):
    num = get_sql_answer(db, "select count(id) from doi_queue where enqueued=false")
    return num

def print_status(do_hybrid=False):
    num_dois = number_total_on_queue(do_hybrid)
    num_waiting = number_waiting_on_queue(do_hybrid)
    print u"There are {} dois in the queue, of which {} ({}%) are waiting to run".format(
        num_dois, num_waiting, int(100*float(num_waiting)/num_dois))

def reset_enqueued():
    q = u"update doi_queue set enqueued=false"
    run_sql(db, q)
    print_status()

def truncate():
    q = "truncate table doi_queue"
    run_sql(db, q)

def num_dynos(process_name):
    heroku_conn = heroku3.from_key(os.getenv("HEROKU_API_KEY"))
    try:
        dynos = heroku_conn.apps()["oadoi"].dynos()[process_name]
    except KeyError:
        dynos = []
    return len(dynos)

def scale_dyno(n, do_hybrid=False):
    process_name = "run" # formation name is from Procfile
    if do_hybrid:
        process_name += "_with_hybrid"

    print "starting with {} dynos".format(num_dynos(process_name))
    print "setting to {} dynos".format(n)
    heroku_conn = heroku3.from_key(os.getenv("HEROKU_API_KEY"))
    app = heroku_conn.apps()['oadoi']
    app.process_formation()[process_name].scale(n)

    print "sleeping for 2 seconds while it kicks in"
    sleep(2)
    print "verifying: now at {} dynos".format(num_dynos(process_name))


def export(do_all=False, do_hybrid=False, filename=None):

    print "logging in to aws"
    conn = boto.ec2.connect_to_region('us-west-2')
    instance = conn.get_all_instances()[0].instances[0]
    ssh_client = sshclient_from_instance(instance, "data/key.pem", user_name="ec2-user")

    print "log in done"


    if filename:
        base_filename = filename.split(".")[0]
    else:
        base_filename = "export_queue"

    if do_all:
        filename = base_filename + "_full.csv"
        table = "export_queue"
        command = """psql {}?ssl=true -c "\copy (select * from {} e) to '{}' WITH (FORMAT CSV, HEADER);" """.format(
            os.getenv("DATABASE_URL"), table, filename)
    elif do_hybrid:
        filename = base_filename + "_hybrid.csv"
        table = "export_queue_with_hybrid"
        command = """psql {}?ssl=true -c "\copy (select * from {}) to '{}' WITH (FORMAT CSV, HEADER);" """.format(
            os.getenv("DATABASE_URL"), table, filename)
    else:
        filename = base_filename + ".csv"
        table = "export_full"
        command = """psql {}?ssl=true -c "\copy (select * from {}) to '{}' WITH (FORMAT CSV, HEADER);" """.format(
            os.getenv("DATABASE_URL"), table, filename)
    print command
    status, stdout, stderr = ssh_client.run(command)
    print status, stdout, stderr

    command = """gzip -c {} > {}.gz;""".format(
        filename, filename)
    print command
    status, stdout, stderr = ssh_client.run(command)
    print status, stdout, stderr

    command = """aws s3 cp {}.gz s3://oadoi-export/{}.gz --acl public-read;""".format(
        filename, filename)
    print command
    status, stdout, stderr = ssh_client.run(command)
    print status, stdout, stderr

    print "now go to *** https://console.aws.amazon.com/s3/object/oadoi-export/{}.gz?region=us-east-1&tab=overview ***".format(
        filename)
    print "public link is at *** https://s3-us-west-2.amazonaws.com/oadoi-export/{}.gz ***".format(
        filename)

    conn.close()


def print_logs(do_hybrid=False):
    process_name = "run" # formation name is from Procfile
    if do_hybrid:
        process_name += "_with_hybrid"

    command = "heroku logs -t | grep {}".format(process_name)
    call(command, shell=True)


def add_dois_to_queue_from_file(filename, do_hybrid=False):
    start = time()

    command = """psql `heroku config:get DATABASE_URL`?ssl=true -c "\copy doi_queue (id) FROM '{}' WITH CSV DELIMITER E'|';" """.format(
        filename)
    call(command, shell=True)

    q = "update doi_queue set id=lower(id)"
    run_sql(db, q)

    print "add_dois_to_queue_from_file done in {} seconds".format(elapsed(start, 1))
    print_status(do_hybrid)


def add_dois_to_queue_from_query(where=None, do_hybrid=False):
    print "adding all dois, this may take a while"
    start = time()

    run_sql(db, "drop table doi_queue cascade")
    create_table_command = "CREATE TABLE doi_queue as (select id, random() as rand, false as enqueued from crossref)"
    if where:
        create_table_command = create_table_command.replace("from crossref)", "from crossref where {})".format(where))
    run_sql(db, create_table_command)
    recreate_commands = """
        alter table doi_queue alter column rand set default random();
        alter table doi_queue alter column enqueued set default false;
        CREATE INDEX doi_queue_enqueued_idx ON doi_queue USING btree (enqueued);
        CREATE INDEX doi_queue_rand_enqueued_idx ON doi_queue USING btree (rand, enqueued);
        CREATE INDEX doi_queue_rand_idx ON doi_queue USING btree (rand);
        CREATE INDEX doi_queue_id_idx ON doi_queue USING btree (id);"""
    for command in recreate_commands.split(";"):
        run_sql(db, command)

    command = """create view export_queue as
     SELECT crossref.id AS doi,
        crossref.response_jsonb ->> 'evidence'::text AS evidence,
        crossref.response_jsonb ->> 'oa_color_long'::text AS oa_color,
        crossref.response_jsonb ->> 'free_fulltext_url'::text AS best_open_url,
        crossref.response_jsonb ->> 'year'::text AS year,
        crossref.response_jsonb ->> 'found_hybrid'::text AS found_hybrid,
        crossref.response_jsonb ->> 'found_green'::text AS found_green,
        crossref.response_jsonb ->> 'error'::text AS error,
        crossref.response_jsonb ->> 'is_boai_license'::text AS is_boai_license,
        replace((crossref.api -> '_source'::text) ->> 'journal'::text, '
    '::text, ''::text) AS journal,
        replace((crossref.api -> '_source'::text) ->> 'publisher'::text, '
    '::text, ''::text) AS publisher,
        (crossref.api -> '_source'::text) ->> 'subject'::text AS subject,
        crossref.response_jsonb ->> 'green_base_collections'::text AS green_base_collections,
        crossref.response_jsonb ->> 'license'::text AS license
       FROM crossref"""
    run_sql(db, command)

    # they are already lowercased
    print "add_dois_to_queue_from_query done in {} seconds".format(elapsed(start, 1))
    print_status(do_hybrid)



def run(parsed_args):
    start = time()
    process_name = "run" # formation name is from Procfile
    if parsed_args.hybrid:
        process_name += "_with_hybrid"
    update = update_registry.get("Crossref."+process_name)
    update.run(**vars(parsed_args))

    print "finished update in {} seconds".format(elapsed(start))


# python doi_queue.py --soup --hybrid --filename=data/dois_juan_accuracy.csv --dynos=20

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run stuff.")
    parser.add_argument('--limit', "-l", nargs="?", type=int, help="how many jobs to do")
    parser.add_argument('--chunk', "-ch", nargs="?", default=10, type=int, help="how many to take off db at once")
    parser.add_argument('--id', nargs="?", type=str, help="id of the one thing you want to update")

    parser.add_argument('--filename', nargs="?", type=str, help="filename with dois, one per line")
    parser.add_argument('--addall', default=False, action='store_true', help="add everything")
    parser.add_argument('--where', nargs="?", type=str, default=None, help="""where string for addall (eg --where="crossref.response_jsonb->>'oa_color_long'='green_only'")""")

    parser.add_argument('--hybrid', default=False, action='store_true', help="if hybrid, else don't include")
    parser.add_argument('--all', default=False, action='store_true', help="do everything")

    parser.add_argument('--reset', default=False, action='store_true', help="do you want to just reset?")
    parser.add_argument('--run', default=False, action='store_true', help="to run the queue")
    parser.add_argument('--status', default=False, action='store_true', help="to print the status")
    parser.add_argument('--dynos', default=None, type=int, help="scale to this many dynos")
    parser.add_argument('--export', default=False, action='store_true', help="export the results")
    parser.add_argument('--logs', default=False, action='store_true', help="export the whole db")
    parser.add_argument('--soup', default=False, action='store_true', help="soup to nuts")
    parsed_args = parser.parse_args()

    if parsed_args.filename:
        truncate()
        add_dois_to_queue_from_file(parsed_args.filename, parsed_args.hybrid)

    if parsed_args.addall or parsed_args.where:
        truncate()
        add_dois_to_queue_from_query(parsed_args.where, parsed_args.hybrid)

    if parsed_args.soup:
        scale_dyno(parsed_args.dynos, parsed_args.hybrid)
        monitor_till_done(parsed_args.hybrid)
        scale_dyno(0, parsed_args.hybrid)
        export(parsed_args.all, parsed_args.hybrid, parsed_args.filename)
    else:
        if parsed_args.dynos != None:  # to tell the difference from setting to 0
            scale_dyno(parsed_args.dynos, parsed_args.hybrid)
            if parsed_args.dynos > 0:
                print_logs(parsed_args.hybrid)

    if parsed_args.reset:
        reset_enqueued(parsed_args.hybrid)

    if parsed_args.status:
        print_status(parsed_args.hybrid)

    if parsed_args.logs:
        print_logs(parsed_args.hybrid)

    if parsed_args.export:
        export(parsed_args.all, parsed_args.hybrid, parsed_args.filename)



    if parsed_args.run:
        run(parsed_args)



