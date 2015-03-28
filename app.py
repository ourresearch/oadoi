from flask import Flask
import redis
import os

app = Flask(__name__)

my_redis = redis.from_url(
                    os.getenv("REDIS_URL", "redis://127.0.0.1:6379"),
                    db=10)
