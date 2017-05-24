from celery import Celery
from db import Records, db
import json
import hashlib


app = Celery('tasks', broker='redis://127.0.0.1:6379/0')


@app.task(ignore_result=True, task_acks_late=True)
def add(txt):
    r = Records(
            timestamp=int(time.time()),
            message_id=hashlib.sha1(txt).hexdigest()[0:7],
            record=txt
    )
