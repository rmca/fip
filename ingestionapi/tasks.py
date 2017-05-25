from celery import Celery
from db import Records, db
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

import json
import uuid
import os
import time
import structlog
import socket


broker = os.environ.get('TASK_BROKER', 'redis://redis:6379/0')
app = Celery('tasks', broker=broker)

logger = structlog.get_logger()
hostname = socket.gethostname()


@app.task(ignore_result=True, task_acks_late=True)
def add(txt, timefunc=time.time, uuidfunc=lambda: uuid.uuid4().hex):
    try:
        r = Records(
            timestamp=int(timefunc()),
            message_id=uuidfunc(),
            record=txt
        )
        db.session.add(r)
        db.session.commit()
    except IntegrityError:
        # Task was maybe retried and had already succeeded
        # Allow the execution to succeed.
        db.session.rollback()
        pass
    except SQLAlchemyError as e:
        logger.info(task_failed=1, hostname=hostname, exception=str(e))
        raise

    logger.info("Completed task", task_completed=1, hostname=hostname)
    # Otherwise let the task fail and be retried on exception
    # Or succeed .
