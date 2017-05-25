from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

import os

app = Flask(__name__)
db_uri = os.environ.get('SQLALCHEMY_DATABASE_URI')
db_uri = db_uri or 'mysql://root@mysql:3306/falcon'
app.config['SQLALCHEMY_DATABASE_URI'] = db_uri

db = SQLAlchemy(app)
migrate = Migrate(app, db)


class Records(db.Model):

    timestamp = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.String(32), primary_key=True)
    record = db.Column(db.Text)
