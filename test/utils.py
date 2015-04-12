import redis
import os

REDIS_UNITTEST_DATABASE_NUMBER = 15

def slow(f):
    f.slow = True
    return f

def http(f):
    f.http = True
    return f

def setup_redis_for_unittests():
    # do the same thing for the redis db, set up the test redis database.  We're using DB Number 8
    r = redis.from_url("redis://localhost:6379", db=REDIS_UNITTEST_DATABASE_NUMBER)
    r.flushdb()
    return r

def open_file_from_data_dir(filename):
    current_dir = os.path.dirname(__file__)
    rel_path = "data/{}".format(filename)
    absolute_path = os.path.join(current_dir, rel_path)
    handle = open(absolute_path, "r")   
    return handle 