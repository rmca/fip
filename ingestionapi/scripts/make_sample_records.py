from db import db, Records
import time
import uuid

make_time = lambda: int(time.time())
make_uuid = lambda: str(uuid.uuid4().hex)

# Create a bunch of boring records.
# If you get tired of waiting just hit ^C
for i in xrange(100000):
    r = Records(timestamp=make_time(), message_id=make_uuid(), record='a'*1000)
    db.session.add(r)
    # Commit records periodically.
    if i % 1000 == 0:
        db.session.commit()

db.session.commit()
