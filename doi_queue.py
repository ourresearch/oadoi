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
from pprint import pprint


from app import db
from jobs import update_registry
import jobs_defs # needs to be imported so the definitions get loaded into the registry
from util import elapsed
from util import run_sql
from util import get_sql_answer
from util import get_sql_answers
from util import clean_doi

from publication import Crossref


def monitor_till_done(do_hybrid=False):
    num_total = number_total_on_queue(do_hybrid)
    loop_thresholds = {"short": 10, "long": 5*60, "medium": 60}
    loop_unfinished = {"short": number_unfinished(do_hybrid), "long": number_unfinished(do_hybrid)}
    loop_start_time = {"short": time(), "long": time()}

    print_idle_dynos(do_hybrid)

    while number_unfinished(do_hybrid) > 0:
        for loop in ["short", "long"]:
            if elapsed(loop_start_time[loop]) > loop_thresholds[loop]:
                if loop in ["short", "long"]:
                    num_unfinished_now = number_unfinished(do_hybrid)
                    num_finished_this_loop = loop_unfinished[loop] - num_unfinished_now
                    loop_unfinished[loop] = num_unfinished_now
                    print u"{} finished in the last {} seconds, {} of {} are now finished ({}%)".format(
                        num_finished_this_loop, loop_thresholds[loop],
                        num_total - num_unfinished_now,
                        num_total,
                        int(100*float(num_total - num_unfinished_now)/num_total)
                    )
                    if num_finished_this_loop:
                        minutes_left = float(num_unfinished_now) / num_finished_this_loop * loop_thresholds[loop] / 60
                        print u"\n{}: At this rate, done in {} minutes, which is {} hours".format(
                            loop, round(minutes_left, 1), round(minutes_left/60, 1))
                    loop_start_time[loop] = time()
                    # print_idle_dynos(do_hybrid)
    print "everything is done.  turning off all the dynos"
    scale_dyno(0, do_hybrid)


def number_total_on_queue(do_hybrid):
    num = get_sql_answer(db, "select count(id) from doi_queue")
    return num

def number_waiting_on_queue(do_hybrid):
    num = get_sql_answer(db, "select count(id) from doi_queue where enqueued=FALSE")
    return num

def number_unfinished(do_hybrid):
    num = get_sql_answer(db, "select count(id) from doi_queue where finished is null")
    return num

def print_status(do_hybrid=False):
    num_dois = number_total_on_queue(do_hybrid)
    num_waiting = number_waiting_on_queue(do_hybrid)
    print u"There are {} dois in the queue, of which {} ({}%) are waiting to run".format(
        num_dois, num_waiting, int(100*float(num_waiting)/num_dois))

def reset_enqueued():
    q = u"update doi_queue set enqueue=FALSE"
    run_sql(db, q)
    print_status()

def truncate():
    q = "truncate table doi_queue"
    run_sql(db, q)

def process_name(do_hybrid):
    process_name = "run" # formation name is from Procfile
    if do_hybrid:
        process_name += "_with_hybrid"
    return process_name

def num_dynos(do_hybrid):
    heroku_conn = heroku3.from_key(os.getenv("HEROKU_API_KEY"))
    num_dynos = 0
    try:
        dynos = heroku_conn.apps()["oadoi"].dynos()[process_name(do_hybrid)]
        num_dynos = len(dynos)
    except (KeyError, TypeError) as e:
        pass
    return num_dynos

def print_idle_dynos(do_hybrid=False):
    heroku_conn = heroku3.from_key(os.getenv("HEROKU_API_KEY"))
    app = heroku_conn.apps()['oadoi']
    running_dynos = []
    try:
        running_dynos = [dyno for dyno in app.dynos() if dyno.name.startswith(process_name(do_hybrid))]
    except (KeyError, TypeError) as e:
        pass

    dynos_still_working = get_sql_answers(db, "select dyno from doi_queue where started is not null and finished is null")
    dynos_still_working_names = [n for n in dynos_still_working]

    print "dynos still running:", [d.name for d in running_dynos if d.name in dynos_still_working_names]
    # print "dynos stopped:", [d.name for d in running_dynos if d.name not in dynos_still_working_names]
    # kill_list = [d.kill() for d in running_dynos if d.name not in dynos_still_working_names]

def scale_dyno(n, do_hybrid=False):
    print "starting with {} dynos".format(num_dynos(do_hybrid))
    print "setting to {} dynos".format(n)
    heroku_conn = heroku3.from_key(os.getenv("HEROKU_API_KEY"))
    app = heroku_conn.apps()['oadoi']
    app.process_formation()[process_name(do_hybrid)].scale(n)

    print "sleeping for 2 seconds while it kicks in"
    sleep(2)
    print "verifying: now at {} dynos".format(num_dynos(do_hybrid))


def export(do_all=False, do_hybrid=False, filename=None):

    print "logging in to aws"
    conn = boto.ec2.connect_to_region('us-west-2')
    instance = conn.get_all_instances()[0].instances[0]
    ssh_client = sshclient_from_instance(instance, "data/key.pem", user_name="ec2-user")

    print "log in done"


    if filename:
        base_filename = filename.rsplit("/")[-1]
        base_filename = base_filename.split(".")[0]
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

    # also do the non .gz one because easier
    command = """aws s3 cp {} s3://oadoi-export/{} --acl public-read;""".format(
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
    command = "heroku logs -t | grep {}".format(process_name(do_hybrid))
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
    create_table_command = "CREATE TABLE doi_queue as (select id, random() as rand, false as enqueued, null::timestamp as finished, null::timestamp as started, null::text as dyno from crossref)"
    if where:
        create_table_command = create_table_command.replace("from crossref)", "from crossref where {})".format(where))
    run_sql(db, create_table_command)
    recreate_commands = """
        alter table doi_queue alter column rand set default random();
        alter table doi_queue alter column enqueued set default false;
        CREATE INDEX doi_queue_enqueued_idx ON doi_queue USING btree (enqueued);
        CREATE INDEX doi_queue_rand_enqueued_idx ON doi_queue USING btree (rand, enqueued);
        CREATE INDEX doi_queue_rand_idx ON doi_queue USING btree (rand);
        CREATE INDEX doi_queue_id_idx ON doi_queue USING btree (id);
        CREATE INDEX doi_queue_finished_idx ON doi_queue USING btree (finished);
        CREATE INDEX doi_queue_started_idx ON doi_queue USING btree (started);"""
    for command in recreate_commands.split(";"):
        run_sql(db, command)

    command = """create view export_queue as
     SELECT id AS doi,
        updated_response_with_hybrid AS updated,
        response_jsonb->>'evidence' AS evidence,
        response_jsonb->>'oa_color_long' AS oa_color,
        response_jsonb->>'free_fulltext_url' AS best_open_url,
        response_jsonb->>'year' AS year,
        response_jsonb->>'found_hybrid' AS found_hybrid,
        response_jsonb->>'found_green' AS found_green,
        response_jsonb->>'error' AS error,
        response_jsonb->>'is_boai_license' AS is_boai_license,
        replace(api->'_source'->>'journal', '
    ', '') AS journal,
        replace(api->'_source'->>'publisher', '
    ', '') AS publisher,
        api->'_source'->>'title' AS title,
        api->'_source'->>'subject' AS subject,
        response_jsonb->>'green_base_collections' AS green_base_collections,
        response_jsonb->>'_open_base_ids' AS open_base_ids,
        response_jsonb->>'_closed_base_ids' AS closed_base_ids,
        response_jsonb->>'license' AS license
       FROM crossref where id in (select id from doi_queue)"""

    command_with_hybrid = command.replace("response_jsonb", "response_with_hybrid")
    run_sql(db, command)

    # they are already lowercased
    print "add_dois_to_queue_from_query done in {} seconds".format(elapsed(start, 1))
    print_status(do_hybrid)



def run(parsed_args):
    start = time()
    update = update_registry.get("Crossref."+process_name(parsed_args.hybrid))
    if parsed_args.doi:
        parsed_args.id = clean_doi(parsed_args.doi)
        parsed_args.doi = None

    print "\n\nparsed_args", parsed_args
    update.run(**vars(parsed_args))

    print "finished update in {} seconds".format(elapsed(start))

    my_pub = Crossref.query.get(parsed_args.id)
    if parsed_args.hybrid:
        resp = my_pub.response_with_hybrid
    else:
        resp = my_pub.response_jsonb
    pprint(resp)
    return resp


# python doi_queue.py --hybrid --filename=data/dois_juan_accuracy.csv --dynos=40 --soup

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run stuff.")
    parser.add_argument('--id', nargs="?", type=str, help="id of the one thing you want to update (case sensitive)")
    parser.add_argument('--doi', nargs="?", type=str, help="id of the one thing you want to update (case insensitive)")

    parser.add_argument('--filename', nargs="?", type=str, help="filename with dois, one per line")
    parser.add_argument('--addall', default=False, action='store_true', help="add everything")
    parser.add_argument('--where', nargs="?", type=str, default=None, help="""where string for addall (eg --where="response_jsonb->>'oa_color_long'='green_only'")""")

    parser.add_argument('--hybrid', default=False, action='store_true', help="if hybrid, else don't include")
    parser.add_argument('--all', default=False, action='store_true', help="do everything")

    parser.add_argument('--reset', default=False, action='store_true', help="do you want to just reset?")
    parser.add_argument('--run', default=False, action='store_true', help="to run the queue")
    parser.add_argument('--status', default=False, action='store_true', help="to print the status")
    parser.add_argument('--dynos', default=None, type=int, help="scale to this many dynos")
    parser.add_argument('--export', default=False, action='store_true', help="export the results")
    parser.add_argument('--logs', default=False, action='store_true', help="print out logs")
    parser.add_argument('--monitor', default=False, action='store_true', help="monitor till done, then turn off dynos")
    parser.add_argument('--soup', default=False, action='store_true', help="soup to nuts")
    parsed_args = parser.parse_args()

    if parsed_args.filename:
        if num_dynos(parsed_args.hybrid) > 0:
            scale_dyno(0, parsed_args.hybrid)
        truncate()
        add_dois_to_queue_from_file(parsed_args.filename, parsed_args.hybrid)

    if parsed_args.addall or parsed_args.where:
        if num_dynos(parsed_args.hybrid) > 0:
            scale_dyno(0, parsed_args.hybrid)
        truncate()
        add_dois_to_queue_from_query(parsed_args.where, parsed_args.hybrid)

    if parsed_args.soup:
        if num_dynos(parsed_args.hybrid) > 0:
            scale_dyno(0, parsed_args.hybrid)
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

    if parsed_args.monitor:
        monitor_till_done(parsed_args.hybrid)
        scale_dyno(0, parsed_args.hybrid)

    if parsed_args.logs:
        print_logs(parsed_args.hybrid)

    if parsed_args.export:
        export(parsed_args.all, parsed_args.hybrid, parsed_args.filename)

    if parsed_args.id or parsed_args.doi or parsed_args.run:
        run(parsed_args)

