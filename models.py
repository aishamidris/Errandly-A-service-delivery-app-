from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()


# ==========================================
# ORDER STATUS
# ==========================================

ORDER_STATUS = [
    "Pending Pickup",
    "Picked Up",
    "Verification In Progress",
    "Awaiting Customer Approval",
    "Verified",
    "Washing",
    "Ironing",
    "Ready For Payment",
    "Paid",
    "Ready For Delivery",
    "Out For Delivery",
    "Delivered"
]


# ==========================================
# USER MODEL
# ==========================================

class User(UserMixin, db.Model):
    __tablename__ = "users"

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

    notifications = db.relationship(
    "Notification",
    back_populates="user",
    cascade="all, delete-orphan"
)


# ==========================================
# LAUNDRY ORDER
# ==========================================

class LaundryOrder(db.Model):
    __tablename__ = "laundry_orders"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    # wash_press / pressing / subscription
    service_type = db.Column(
        db.String(30),
        nullable=False
    )

    pickup_date = db.Column(
        db.Date,
        nullable=False
    )

    delivery_date = db.Column(
        db.Date,
        nullable=False
    )

    # Customer's calculated total
    submitted_total = db.Column(
        db.Integer,
        nullable=False,
        default=0
    )

    # Manager's verified total
    verified_total = db.Column(
        db.Integer,
        nullable=False,
        default=0
    )

    payment_status = db.Column(
        db.String(20),
        nullable=False,
        default="UNPAID"
    )

    order_status = db.Column(
        db.String(40),
        nullable=False,
        default=ORDER_STATUS[0]
    )

    manager_note = db.Column(
        db.Text
    )

    customer_approved = db.Column(
        db.Boolean,
        default=False
    )

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow
    )

    user = db.relationship(
        "User",
        backref=db.backref(
            "laundry_orders",
            lazy=True
        )
    )


# ==========================================
# ORDER ITEMS
# ==========================================

class OrderItem(db.Model):
    __tablename__ = "order_items"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    order_id = db.Column(
        db.Integer,
        db.ForeignKey("laundry_orders.id"),
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
        default=0
    )

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow
    )

    order = db.relationship(
    "LaundryOrder",
    backref=db.backref(
        "items",
        lazy=True,
        cascade="all, delete-orphan"
    )

    )

class Notification(db.Model):

    __tablename__ = "notifications"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    title = db.Column(
        db.String(150),
        nullable=False
    )

    message = db.Column(
        db.Text,
        nullable=False
    )

    is_read = db.Column(
        db.Boolean,
        default=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    user = db.relationship(
        "User",
        back_populates="notifications"
    )