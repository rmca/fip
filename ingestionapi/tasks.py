from celery import Celery
import json

app = Celery('tasks', broker='redis://127.0.0.1:6379/0')

import sqlite3
conn = sqlite3.connect('example.db')

c = conn.cursor()
c.execute("CREATE TABLE data (data text)")
conn.commit()

@app.task(ignore_result=True, task_acks_late=True)
def add(txt):
    cursor = conn.cursor()
    cursor.executemany("INSERT INTO data VALUES(?)", [(txt,)])
    conn.commit()
