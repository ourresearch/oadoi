from time import time
from app import db
import argparse
from jobs import update_registry
from util import elapsed

# needs to be imported so the definitions get loaded into the registry
import jobs_defs


"""
examples of calling this:

# update everything
python update.py Person.refresh --limit 10 --chunk 5 --rq

# update one thing not using rq
python update.py Package.test --id 0000-1111-2222-3333

"""

def parse_update_optional_args(parser):
    # just for updating lots
    parser.add_argument('--limit', "-l", nargs="?", type=int, help="how many jobs to do")
    parser.add_argument('--chunk', "-ch", nargs="?", type=int, help="how many to take off db at once")
    parser.add_argument('--after', nargs="?", type=str, help="minimum id or id start, ie 0000-0001")
    parser.add_argument('--rq', action="store_true", default=False, help="do jobs in this thread")
    parser.add_argument('--order', action="store_true", default=True, help="order them")
    parser.add_argument('--append', action="store_true", default=False, help="append, dont' clear queue")

    # just for updating one
    parser.add_argument('--id', nargs="?", type=str, help="id of the one thing you want to update")
    parser.add_argument('--doi', nargs="?", type=str, help="doi of the one thing you want to update")

    # parse and run
    parsed_args = parser.parse_args()
    return parsed_args


def run_update(parsed_args):
    update = update_registry.get(parsed_args.fn)

    start = time()

    #convenience method for handling an doi
    if parsed_args.doi:
        from publication import Crossref
        from util import clean_doi

        my_pub = db.session.query(Crossref).filter(Crossref.id==clean_doi(parsed_args.doi)).first()
        parsed_args.id = my_pub.id
        print u"Got database for this doi: {}".format(my_pub.id)

    update.run(
        use_rq=parsed_args.rq,
        obj_id=parsed_args.id,  # is empty unless updating just one row
        min_id=parsed_args.after,  # is empty unless minimum id
        num_jobs=parsed_args.limit,
        append=parsed_args.append,
        chunk_size=parsed_args.chunk
    )

    db.session.remove()
    print "finished update in {} secconds".format(elapsed(start))



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run stuff.")
    # for everything
    parser.add_argument('fn', type=str, help="what function you want to run")
    parsed_args = parse_update_optional_args(parser)
    run_update(parsed_args)


