from app import db
from datetime import datetime

class User(db.Model):
    id = db.Column(db.String(64), primary_key=True)
    username = db.Column(db.String(128), nullable=False)
    currency = db.relationship('UserCurrency', backref='user', lazy=True)
    event_wins = db.relationship('EventWinner', backref='user', lazy=True)

class UserCurrency(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(64), db.ForeignKey('user.id'), nullable=False)
    currency = db.Column(db.Integer, default=0)
    server_id = db.Column(db.String(64), nullable=False)

class EventWinner(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(64), db.ForeignKey('user.id'), nullable=False)
    server_id = db.Column(db.String(64), nullable=False)
    event_date = db.Column(db.DateTime, default=datetime.utcnow)