import os

bind = f"0.0.0.0:{os.getenv('FLASK_PORT', '5001')}"
workers = 1
timeout = 180


def post_worker_init(worker):
    worker.wsgi.extensions["container"].initialize()
