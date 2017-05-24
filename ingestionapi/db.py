from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root@127.0.0.1:5306/falcon'

db = SQLAlchemy(app)
migrate = Migrate(app, db)

class Records(db.Model):

    timestamp = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.String(32), primary_key=True)
    record = db.Column(db.Text)
    
