from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120))
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    cash = db.Column(db.Float, default=10000.0)

    operations = db.relationship('Operation', backref='user', lazy=True)
    holdings = db.relationship('Holding', backref='user', lazy=True)


class Asset(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ticker = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(200))
    last_price = db.Column(db.Float)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    holdings = db.relationship('Holding', backref='asset', lazy=True)


class Operation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'))
    type = db.Column(db.String(10))
    quantity = db.Column(db.Float)
    price = db.Column(db.Float)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


class Holding(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'))
    quantity = db.Column(db.Float, default=0.0)
    avg_price = db.Column(db.Float, default=0.0)