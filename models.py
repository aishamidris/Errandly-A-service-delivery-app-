from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime


db = SQLAlchemy()


class User(UserMixin, db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    name = db.Column(
        db.String(100),
        nullable=False
    )

    email = db.Column(
        db.String(120),
        unique=True,
        nullable=False
    )

    phone = db.Column(
        db.String(20),
        nullable=False
    )

    address = db.Column(
        db.String(250),
        nullable=False
    )

    password = db.Column(
        db.String(250),
        nullable=False
    )

    role = db.Column(
        db.String(20),
        nullable=False,
        default="customer"
    )


class LaundryOrder(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )

    service_type = db.Column(
        db.String(50),
        nullable=False
    )

    submitted_total = db.Column(
        db.Integer,
        nullable=False
    )

    verified_total = db.Column(
        db.Integer,
        nullable=True
    )

    pickup_date = db.Column(
        db.Date,
        nullable=False
    )

    delivery_date = db.Column(
        db.Date,
        nullable=False
    )

    verification_status = db.Column(
        db.String(30),
        nullable=False,
        default="Pending Verification"
    )

    order_status = db.Column(
        db.String(30),
        nullable=False,
        default="Pending"
    )

    payment_status = db.Column(
        db.String(30),
        nullable=False,
        default="Unpaid"
    )

    manager_note = db.Column(
        db.Text,
        nullable=True
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    user = db.relationship(
        "User",
        backref="laundry_orders"
    )

    items = db.relationship(
        "OrderItem",
        backref="order",
        cascade="all, delete-orphan"
    )


class OrderItem(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    order_id = db.Column(
        db.Integer,
        db.ForeignKey("laundry_order.id"),
        nullable=False
    )

    item_name = db.Column(
        db.String(100),
        nullable=False
    )

    price = db.Column(
        db.Integer,
        nullable=False
    )

    submitted_quantity = db.Column(
        db.Integer,
        nullable=False
    )

    verified_quantity = db.Column(
        db.Integer,
        nullable=True
    )