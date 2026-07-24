from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin


db = SQLAlchemy()


class User(UserMixin, db.Model):

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(100), nullable=False)

    email = db.Column(db.String(120), unique=True, nullable=False)

    phone = db.Column(db.String(20), nullable=False)

    address = db.Column(db.String(250), nullable=False)

    password = db.Column(db.String(250), nullable=False)

    role = db.Column(
        db.String(20),
        nullable=False,
        default="customer"
    )