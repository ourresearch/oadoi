from sqlalchemy.exc import OperationalError
from sqlalchemy.sql import text    

import redis
import os

REDIS_UNITTEST_DATABASE_NUMBER = 15

def slow(f):
    f.slow = True
    return f

def http(f):
    f.http = True
    return f



def open_file_from_data_dir(filename):
    current_dir = os.path.dirname(__file__)
    rel_path = "data/{}".format(filename)
    absolute_path = os.path.join(current_dir, rel_path)
    handle = open(absolute_path, "r")   
    return handle 


def setup_redis_for_unittests():
    # do the same thing for the redis db, set up the test redis database.  We're using DB Number 8
    r = redis.from_url("redis://localhost:6379", db=REDIS_UNITTEST_DATABASE_NUMBER)
    r.flushdb()
    return r


# from http://www.sqlalchemy.org/trac/wiki/UsageRecipes/DropEverything
# with a few changes

def drop_everything(db, app):
    from sqlalchemy.engine import reflection
    from sqlalchemy import create_engine
    from sqlalchemy.schema import (
        MetaData,
        Table,
        DropTable,
        ForeignKeyConstraint,
        DropConstraint,
        )

    conn = db.session()

    engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'])
    inspector = reflection.Inspector.from_engine(engine)

    # gather all data first before dropping anything.
    # some DBs lock after things have been dropped in 
    # a transaction.
    
    metadata = MetaData()

    tbs = []
    all_fks = []

    for table_name in inspector.get_table_names():
        fks = []
        for fk in inspector.get_foreign_keys(table_name):
            if not fk['name']:
                continue
            fks.append(
                ForeignKeyConstraint((),(),name=fk['name'])
                )
        t = Table(table_name,metadata,*fks)
        tbs.append(t)
        all_fks.extend(fks)

    for fkc in all_fks:
        conn.execute(DropConstraint(fkc))

    for table in tbs:
        conn.execute(DropTable(table))

    db.session.commit()    


def setup_postgres_for_unittests(db, app):
    if not "localhost" in app.config["SQLALCHEMY_DATABASE_URI"]:
        assert(False), "Not running this unittest because SQLALCHEMY_DATABASE_URI is not on localhost"

    drop_everything(db, app)
    db.create_all()
    return db


def teardown_postgres_for_unittests(db):
    db.session.close_all()
