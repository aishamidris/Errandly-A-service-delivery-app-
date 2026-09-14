from flask import Flask, render_template, redirect, url_for, flash, request, session, abort
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_wtf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, LaundryOrder, OrderItem, ORDER_STATUS, Notification, ServiceItem
from constants import LAUNDRY_PRICES, SERVICE_TYPES, PAYMENT_STATUS
from forms import RegisterForm, LoginForm, LaundryOrderForm
import paystack_service
from datetime import datetime, timedelta
from functools import wraps
from dotenv import load_dotenv
import requests
import os

# Load variables from .env into the environment.
# Must run before anything below reads os.environ.get(...).
load_dotenv()


app = Flask(__name__)


# =========================
# APP CONFIGURATION
# =========================

app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY")

if not app.config["SECRET_KEY"]:
    raise RuntimeError(
        "SECRET_KEY is not set. Create a .env file (see .env.example) "
        "and set SECRET_KEY before running the app."
    )

database_url = os.environ.get("DATABASE_URL", "sqlite:///errandly.db")

# Some providers (Neon, old Heroku-style URLs) hand out a connection
# string starting with "postgres://", but SQLAlchemy 2.x only
# recognizes "postgresql://" - swap it so DATABASE_URL works as-is
# without needing to hand-edit whatever your host gives you.
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# =========================
# SESSION / COOKIE SECURITY
# =========================

# Prevents JavaScript from reading the session cookie (mitigates XSS
# stealing a logged-in session).
app.config["SESSION_COOKIE_HTTPONLY"] = True

# Blocks the cookie from being sent on cross-site requests, which is
# a second layer of CSRF defense alongside CSRFProtect above.
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# Only send the cookie over HTTPS. Set SESSION_COOKIE_SECURE=True in
# your production .env once you're deployed behind HTTPS - leave it
# False for local http://127.0.0.1 development, or your session
# cookie will never be sent and you'll get logged out immediately.
app.config["SESSION_COOKIE_SECURE"] = os.environ.get(
    "SESSION_COOKIE_SECURE", "False"
) == "True"

# Debug mode must be explicitly opted into - never default to on.
# debug=True exposes a live Python console (the Werkzeug debugger)
# to anyone who can trigger a 500 error, which is a remote code
# execution risk if this ever runs on a public server.
app.config["DEBUG"] = os.environ.get("FLASK_DEBUG", "False") == "True"

# =========================
# PAYSTACK CONFIGURATION
# =========================

app.config["PAYSTACK_SECRET_KEY"] = os.environ.get("PAYSTACK_SECRET_KEY")

app.config["PAYSTACK_PUBLIC_KEY"] = os.environ.get("PAYSTACK_PUBLIC_KEY")

# =========================
# INITIALIZE DATABASE
# =========================

db.init_app(app)


# =========================
# ENABLE APP-WIDE CSRF PROTECTION
# =========================
# This protects every POST/PUT/PATCH/DELETE route, including ones
# like /laundry/<service_type>/items that read raw request.form
# instead of going through a FlaskForm object. Without this, those
# routes have no CSRF protection even though your FlaskForm-based
# routes (register, login) are protected automatically.

csrf = CSRFProtect(app)


# =========================
# INITIALIZE LOGIN MANAGER
# =========================

login_manager = LoginManager()

login_manager.init_app(app)

@app.context_processor
def inject_notification_count():

    unread_count = 0

    if current_user.is_authenticated:

        unread_count = (
            Notification.query
            .filter_by(
                user_id=current_user.id,
                is_read=False
            )
            .count()
        )

    return dict(
        unread_notifications=unread_count
    )


@login_manager.user_loader
def load_user(user_id):

    return db.get_or_404(User, int(user_id))


def admin_required(f):

    @wraps(f)
    def wrapped_view(*args, **kwargs):

        if not current_user.is_authenticated:

            flash(
                "Please log in to access the admin area.",
                "warning"
            )

            return redirect(url_for("login"))

        if current_user.role != "admin":

            flash(
                "You do not have permission to access this page.",
                "danger"
            )

            return redirect(url_for("dashboard"))

        return f(*args, **kwargs)

    return wrapped_view

def create_notification(
    user_id,
    title,
    message,
    order_id=None
):

    notification = Notification(

        user_id=user_id,

        title=title,

        message=message,

        order_id=order_id

    )

    db.session.add(notification)

# =========================
# ROUTES
# =========================


@app.route("/")
def home():
    return render_template("index.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    form = RegisterForm()

    if form.validate_on_submit():

        existing_user = db.session.execute(
            db.select(User).where(User.email == form.email.data)
        ).scalar_one_or_none()

        if existing_user:
            flash(
                "An account with this email already exists. Please log in.",
                "danger"
            )
            return redirect(url_for("login"))

        hashed_password = generate_password_hash(
            form.password.data,
            method="scrypt",
            salt_length=8
        )

        new_user = User(
            name=form.name.data,
            email=form.email.data,
            phone=form.phone.data,
            address=form.address.data,
            password=hashed_password
        )

        db.session.add(new_user)
        db.session.commit()

        login_user(new_user)

        flash("Registration successful!", "success")

        return redirect(url_for("home"))

    return render_template(
        "auth/register.html",
        form=form
    )

@app.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()

    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data

        user = db.session.execute(
            db.select(User).where(User.email == email)
        ).scalar_one_or_none()

        if user and check_password_hash(user.password, password):
            login_user(user)

            flash("Login successful!", "success")

            return redirect(url_for("dashboard"))

        flash("Invalid email or password.", "danger")

    return render_template("auth/login.html", form=form)

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out successfully.", "success")
    return redirect(url_for("home"))


@app.route("/dashboard")
@login_required
def dashboard():

    orders = LaundryOrder.query.filter_by(
        user_id=current_user.id
    ).order_by(
        LaundryOrder.created_at.desc()
    ).all()

    total_orders = len(orders)

    pending_orders = sum(
        1 for order in orders
        if order.order_status not in [
            "Delivered"
        ]
    )

    completed_orders = sum(
        1 for order in orders
        if order.order_status == "Delivered"
    )

    return render_template(
        "dashboard.html",
        orders=orders,
        total_orders=total_orders,
        pending_orders=pending_orders,
        completed_orders=completed_orders
    )



@app.route("/payment/<int:order_id>", methods=["GET", "POST"])
@login_required
def payment(order_id):

    order = db.get_or_404(LaundryOrder, order_id)

    # Make sure this order belongs to the logged-in customer
    if order.user_id != current_user.id:

        flash(
            "You are not authorized to access this payment.",
            "danger"
        )

        return redirect(url_for("dashboard"))

    # Make sure the order is actually ready for payment
    if order.order_status != "Ready For Payment":

        flash(
            "This order is not ready for payment.",
            "warning"
        )

        return redirect(
            url_for(
                "order_details",
                order_id=order.id
            )
        )

    if request.method == "POST":

        callback_url = url_for("payment_callback", _external=True)

        try:
            authorization_url, reference = paystack_service.initialize_transaction(
                order, callback_url
            )

        except paystack_service.PaystackError as e:

            flash(f"Could not start payment: {e}", "danger")

            return redirect(
                url_for("payment", order_id=order.id)
            )

        # Save the reference so the callback can look this order back up
        order.payment_reference = reference
        db.session.commit()

        return redirect(authorization_url)

    return render_template(
        "payments.html",
        order=order
    )


def mark_order_paid(order, transaction_amount_kobo):
    """
    Shared "confirm this order is paid" logic, used by both the
    browser-redirect callback (payment_callback) and the
    server-to-server webhook (payment_webhook) - whichever one hears
    about a successful payment first wins, and the other becomes a
    safe no-op. That matters because the browser redirect alone is
    unreliable: if a customer pays on Paystack's page and then closes
    the tab instead of waiting to be redirected back, payment_callback
    never runs and the order would stay "Unpaid" forever without the
    webhook as a backstop.

    Returns one of:
      "paid"          - just marked paid
      "already_paid"  - no-op, some earlier call already handled this
      "mismatch"      - amount didn't match what we expected; not marked
    """

    if order.payment_status == "PAID":
        return "already_paid"

    expected_kobo = (
        order.verified_total or order.submitted_total
    ) * paystack_service.KOBO_PER_NAIRA

    if transaction_amount_kobo != expected_kobo:
        return "mismatch"

    order.payment_status = "PAID"
    order.order_status = "Paid"
    order.paid_at = datetime.utcnow()

    create_notification(
        order.user_id,
        "Payment Successful",
        f"Payment for Order #{order.id} was received successfully.",
        order_id=order.id
    )

    db.session.commit()

    return "paid"


@app.route("/payment/callback")
@login_required
def payment_callback():

    reference = request.args.get("reference")

    if not reference:
        flash("Payment reference missing.", "danger")
        return redirect(url_for("dashboard"))

    order = LaundryOrder.query.filter_by(
        payment_reference=reference
    ).first()

    if not order:
        flash("We couldn't find this payment.", "danger")
        return redirect(url_for("dashboard"))

    if order.user_id != current_user.id:
        flash("You are not authorized to view this payment.", "danger")
        return redirect(url_for("dashboard"))

    # Already processed - either the customer refreshed this page, or
    # the webhook beat us to it. Either way, nothing left to do.
    if order.payment_status == "PAID":
        flash("This order has already been paid for.", "info")
        return redirect(
            url_for("order_details", order_id=order.id)
        )

    try:
        transaction = paystack_service.verify_transaction(reference)

    except paystack_service.PaystackError as e:

        flash(f"Payment could not be verified: {e}", "danger")

        return redirect(
            url_for("payment", order_id=order.id)
        )

    result = mark_order_paid(order, transaction.get("amount"))

    if result == "mismatch":

        flash(
            "Payment amount mismatch. Please contact support.",
            "danger"
        )

        return redirect(
            url_for("payment", order_id=order.id)
        )

    flash("Payment successful!", "success")

    return redirect(
        url_for("order_details", order_id=order.id)
    )


@app.route("/payment/webhook", methods=["POST"])
@csrf.exempt
def payment_webhook():
    """
    Server-to-server endpoint Paystack calls directly when a payment
    succeeds, independent of whether the customer's browser ever made
    it back to /payment/callback. Register this URL (yourdomain.com
    /payment/webhook) in the Paystack dashboard under
    Settings -> API Keys & Webhooks.

    Exempt from CSRF protection because Paystack's server can't send
    a CSRF token - the HMAC signature check below is what verifies
    this request is genuinely from Paystack instead.
    """

    raw_body = request.get_data()

    signature = request.headers.get("x-paystack-signature", "")

    if not paystack_service.verify_webhook_signature(raw_body, signature):
        # Not signed with our secret key - reject without processing.
        abort(401)

    event = request.get_json(silent=True) or {}

    # We only act on successful charges; acknowledge everything else
    # so Paystack doesn't keep retrying events we don't handle.
    if event.get("event") != "charge.success":
        return "", 200

    data = event.get("data", {})

    order = LaundryOrder.query.filter_by(
        payment_reference=data.get("reference")
    ).first()

    if order:
        mark_order_paid(order, data.get("amount"))

    # Always 200 once the signature checks out - Paystack retries on
    # non-2xx responses, and a retry won't fix a reference we don't
    # recognize.
    return "", 200


@app.route("/admin")
@admin_required
def admin_dashboard():

    search = request.args.get("search", "").strip()

    status = request.args.get("status", "")

    query = LaundryOrder.query

    # Search customer name or phone
    if search:

        query = query.join(User).filter(

            db.or_(

                User.name.ilike(f"%{search}%"),

                User.phone.ilike(f"%{search}%")

            )

        )

    # Filter by status

    if status:

        query = query.filter(

            LaundryOrder.order_status == status

        )

    orders = query.order_by(

        LaundryOrder.created_at.desc()

    ).all()

    total_orders = LaundryOrder.query.count()

    pending_orders = LaundryOrder.query.filter_by(
        order_status="Pending Pickup"
    ).count()

    verification_orders = LaundryOrder.query.filter_by(
        order_status="Verification In Progress"
    ).count()

    ready_for_payment = LaundryOrder.query.filter_by(
        order_status="Ready For Payment"
    ).count()

    completed_orders = LaundryOrder.query.filter_by(
        order_status="Delivered"
    ).count()

    return render_template(
    "admin/dashboard.html",
    orders=orders,
    search=search,
    status=status,
    order_statuses=ORDER_STATUS,
    total_orders=total_orders,
    pending_orders=pending_orders,
    verification_orders=verification_orders,
    ready_for_payment=ready_for_payment,
    completed_orders=completed_orders
)


@app.route("/admin/order/<int:order_id>", methods=["GET", "POST"])
@admin_required
def admin_order_details(order_id):

    order = db.get_or_404(LaundryOrder, order_id)

    # ==========================================
    # SAVE VERIFICATION
    # ==========================================

    if request.method == "POST":

        verified_total = 0

        # ------------------------------------------
        # Verify every item
        # ------------------------------------------

        for item in order.items:

            quantity_string = request.form.get(
                f"verified_quantity_{item.id}"
            )

            try:
                verified_quantity = int(quantity_string)

            except (TypeError, ValueError):
                verified_quantity = 0

            # Prevent negative quantities
            if verified_quantity < 0:
                verified_quantity = 0

            # Save verified quantity
            item.verified_quantity = verified_quantity

            # Calculate verified subtotal
            verified_total += (
                item.price * verified_quantity
            )

        # ------------------------------------------
        # Save verified total
        # ------------------------------------------

        order.verified_total = verified_total

        # ------------------------------------------
        # Save manager note
        # ------------------------------------------

        order.manager_note = request.form.get(
            "manager_note"
        )

        # ------------------------------------------
        # Reset customer approval
        # ------------------------------------------

        order.customer_approved = False

        # ------------------------------------------
        # Move order to customer approval
        # ------------------------------------------

        order.order_status = "Awaiting Customer Approval"

        create_notification(order.user_id, "Laundry Verification Complete", f"Order #{order.id} has been verified. Please review and approve it.", order_id=order.id)

        db.session.commit()

        flash(
            f"Order #{order.id} verified successfully. "
            "Waiting for customer approval.",
            "success"
        )

        return redirect(
            url_for(
                "admin_order_details",
                order_id=order.id
            )
        )

    # ==========================================
    # DISPLAY ORDER
    # ==========================================

    return render_template(
        "admin/order_details.html",
        order=order,
        order_statuses=ORDER_STATUS
    )

@app.route("/admin/order/<int:order_id>/status", methods=["POST"])
@admin_required
def update_order_status(order_id):

    order = db.get_or_404(LaundryOrder, order_id)

    new_status = request.form.get("order_status")

    if not new_status:
        flash("Please select an order status.", "danger")
        return redirect(
            url_for("admin_order_details", order_id=order.id)
        )

    # Make sure the status is valid
    if new_status not in ORDER_STATUS:
        flash("Invalid order status.", "danger")
        return redirect(
            url_for("admin_order_details", order_id=order.id)
        )

    # Update order status
    order.order_status = new_status

    # If order is marked as Paid,
    # automatically update payment status too.
    if new_status == "Paid":
        order.payment_status = "PAID"

    # ============================
# SEND CUSTOMER NOTIFICATION
# ============================

    notification_messages = {

        "Pending Pickup":
            "Your laundry order has been received and is waiting for pickup.",

        "Picked Up":
            "Your laundry has been picked up successfully.",

        "Verification In Progress":
            "Your laundry is currently being verified by our staff.",

        "Awaiting Customer Approval":
            "Please review and approve your verified laundry items.",

        "Verified":
            "Thank you. Your laundry has been verified and approved.",

        "Washing":
            "Your laundry is currently being washed.",

        "Ironing":
            "Your clothes are now being ironed.",

        "Ready For Payment":
            "Your laundry is ready. Please complete payment.",

        "Paid":
            "Payment received successfully.",

        "Ready For Delivery":
            "Your laundry has been packed and is ready for delivery.",

        "Out For Delivery":
            "Good news! Your laundry is on the way.",

        "Delivered":
            "Your laundry has been delivered successfully."

    }

    create_notification(

        order.user_id,

        f"Order #{order.id}",

        notification_messages.get(
            new_status,
            f"Your order status changed to {new_status}."
        ),

        order_id=order.id

    )

    db.session.commit()

    flash(
        f"Order #{order.id} status updated to {new_status}.",
        "success"
    )

    return redirect(
        url_for("admin_order_details", order_id=order.id)
    )

# ==========================================================
# ADMIN - CUSTOMER MANAGEMENT
# ==========================================================

@app.route("/admin/customers")
@admin_required
def admin_customers():

    customers = db.session.execute(
        db.select(User)
        .where(User.role == "customer")
        .order_by(User.name)
    ).scalars().all()

    return render_template(
        "admin/customers.html",
        customers=customers
    )

# ==========================================================
# ADMIN - CUSTOMER PROFILE
# ==========================================================

@app.route("/admin/customer/<int:user_id>")
@admin_required
def admin_customer_details(user_id):

    customer = db.get_or_404(User, user_id)

    orders = db.session.execute(
        db.select(LaundryOrder)
        .where(LaundryOrder.user_id == customer.id)
        .order_by(LaundryOrder.created_at.desc())
    ).scalars().all()

    total_orders = len(orders)

    completed_orders = sum(
        1 for order in orders
        if order.order_status == "Delivered"
    )

    pending_orders = sum(
        1 for order in orders
        if order.order_status != "Delivered"
    )

    total_spent = sum(
        order.submitted_total
        for order in orders
        if order.payment_status == "PAID"
    )

    return render_template(
        "admin/customer_details.html",
        customer=customer,
        orders=orders,
        total_orders=total_orders,
        completed_orders=completed_orders,
        pending_orders=pending_orders,
        total_spent=total_spent
    )


# ==========================================================
# CUSTOMER APPROVES VERIFIED ORDER
# ==========================================================

@app.route("/order/<int:order_id>/approve", methods=["POST"])
@login_required
def approve_order(order_id):

    order = db.get_or_404(
        LaundryOrder,
        order_id
    )

    # ------------------------------------------
    # Security check
    # ------------------------------------------

    if order.user_id != current_user.id:

        flash(
            "You are not authorized to approve this order.",
            "danger"
        )

        return redirect(
            url_for("dashboard")
        )

    # ------------------------------------------
    # Make sure order is waiting for approval
    # ------------------------------------------

    if order.order_status != "Awaiting Customer Approval":

        flash(
            "This order is not currently awaiting approval.",
            "warning"
        )

        return redirect(
            url_for(
                "order_details",
                order_id=order.id
            )
        )

    # ------------------------------------------
    # Make sure verification exists
    # ------------------------------------------

    if order.verified_total is None:

        flash(
            "This order has not been verified yet.",
            "danger"
        )

        return redirect(
            url_for(
                "order_details",
                order_id=order.id
            )
        )

    # ------------------------------------------
    # Approve order
    # ------------------------------------------

    order.customer_approved = True

    order.order_status = "Verified"

    create_notification(

    current_user.id,

    "Verification Approved",

    f"You approved the verification for Order #{order.id}. Your laundry will now be processed.",

    order_id=order.id

        )

    db.session.commit()

    flash(
        "Your laundry order has been approved successfully!",
        "success"
    )

    return redirect(url_for("order_details", order_id=order.id)
    )


@app.route("/laundry")
@login_required
def laundry():

    return render_template(
        "laundry/home.html"
    )


@app.route("/laundry/<service_type>/items", methods=["GET", "POST"])
@login_required
def laundry_items(service_type):

    # Make sure the service type is valid
    if service_type not in LAUNDRY_PRICES:
        flash("Invalid laundry service selected.", "danger")
        return redirect(url_for("laundry"))

    # Pull live, active prices from the database instead of the
    # hardcoded LAUNDRY_PRICES dict. Admin-edited prices and newly
    # added items show up here immediately; deactivated items don't.
    service_items = ServiceItem.query.filter_by(
        service_type=service_type,
        is_active=True
    ).order_by(ServiceItem.display_name).all()

    if not service_items:
        flash(
            "This service currently has no items available. "
            "Please check back later.",
            "warning"
        )
        return redirect(url_for("laundry"))

    if request.method == "POST":

        selected_items = []

        total_price = 0

        for service_item in service_items:

            try:
                quantity = int(request.form.get(service_item.item_name, 0))
            except (TypeError, ValueError):
                quantity = 0

            if quantity > 0:

                selected_items.append({
                    "item_name": service_item.item_name,
                    "display_name": service_item.display_name,
                    "quantity": quantity,
                    "price": service_item.price,
                    "subtotal": quantity * service_item.price
                })

                total_price += quantity * service_item.price

        if not selected_items:

            flash(
                "Please add at least one item to your order.",
                "danger"
            )

            return render_template(
                "laundry/items.html",
                service_type=service_type,
                service_items=service_items
            )

        # Store the order temporarily in the session
        session["laundry_order"] = {
            "service_type": service_type,
            "items": selected_items,
            "total_price": total_price
        }

        return redirect(url_for("laundry_schedule"))

    return render_template(
        "laundry/items.html",
        service_type=service_type,
        service_items=service_items
    )


@app.route("/laundry/schedule", methods=["GET", "POST"])
@login_required
def laundry_schedule():

    laundry_order = session.get("laundry_order")

    # Make sure the customer selected items
    if not laundry_order:

        flash(
            "Please select your laundry items first.",
            "warning"
        )

        return redirect(url_for("laundry"))

    if request.method == "POST":

        pickup_date_string = request.form.get("pickup_date")

        if not pickup_date_string:

            flash(
                "Please select a pickup date.",
                "danger"
            )

            return render_template(
                "laundry/schedule.html",
                order=laundry_order
            )

        try:

            pickup_date = datetime.strptime(
                pickup_date_string,
                "%Y-%m-%d"
            ).date()

        except ValueError:

            flash(
                "Invalid pickup date.",
                "danger"
            )

            return render_template(
                "laundry/schedule.html",
                order=laundry_order
            )

        # Don't allow past dates
        if pickup_date < datetime.today().date():

            flash(
                "Pickup date cannot be in the past.",
                "danger"
            )

            return render_template(
                "laundry/schedule.html",
                order=laundry_order
            )

        delivery_date = pickup_date + timedelta(days=3)

        # Store schedule temporarily
        laundry_order["pickup_date"] = pickup_date.strftime("%Y-%m-%d")
        laundry_order["delivery_date"] = delivery_date.strftime("%Y-%m-%d")

        session["laundry_order"] = laundry_order

        return redirect(url_for("laundry_review"))

    return render_template(
        "laundry/schedule.html",
        order=laundry_order
    )


@app.route("/laundry/review", methods=["GET", "POST"])
@login_required
def laundry_review():

    laundry_order = session.get("laundry_order")

    if not laundry_order:

        flash(
            "Your laundry order session has expired.",
            "warning"
        )

        return redirect(url_for("laundry"))

    # CUSTOMER CONFIRMS ORDER
    if request.method == "POST":

        pickup_date = datetime.strptime(
            laundry_order["pickup_date"],
            "%Y-%m-%d"
        ).date()

        delivery_date = datetime.strptime(
            laundry_order["delivery_date"],
            "%Y-%m-%d"
        ).date()

        # Create main order
        new_order = LaundryOrder(

            user_id=current_user.id,

            service_type=laundry_order["service_type"],

            submitted_total=laundry_order["total_price"],

            pickup_date=pickup_date,

            delivery_date=delivery_date,

            order_status="Pending Pickup",

            payment_status="UNPAID"

        )

        db.session.add(new_order)

        # Get database ID
        db.session.flush()

        # Create order items
        for item in laundry_order["items"]:

            new_item = OrderItem(

                order_id=new_order.id,

                item_name=item["item_name"],

                price=item["price"],

                submitted_quantity=item["quantity"],

                verified_quantity=None

            )

            db.session.add(new_item)
        create_notification(

        current_user.id,

        "Laundry Order Created",

        f"Your laundry order #{new_order.id} has been received successfully.",

        order_id=new_order.id

    )

        db.session.commit()

        # Clear temporary order
        session.pop("laundry_order", None)

        flash(
            "Your laundry order has been confirmed successfully!",
            "success"
        )

        return redirect(url_for("dashboard"))

    return render_template(
        "laundry/review.html",
        order=laundry_order,
        current_user=current_user
    )


@app.route("/laundry/wash-press")
@login_required
def wash_press():

    form = LaundryOrderForm()

    return render_template(
        "laundry/wash_press.html",
        form=form,
        laundry_prices=LAUNDRY_PRICES["wash_press"]
    )


@app.route("/laundry/pressing")
@login_required
def pressing():

    form = LaundryOrderForm()

    return render_template(
        "laundry/pressing.html",
        form=form,
        laundry_prices=LAUNDRY_PRICES["pressing"]
    )


@app.route("/laundry/order/<int:order_id>")
@login_required
def order_details(order_id):

    order = db.get_or_404(LaundryOrder, order_id)

    # Make sure the customer can only see their own order
    if order.user_id != current_user.id:
        flash("You are not authorized to view this order.", "danger")
        return redirect(url_for("dashboard"))

    return render_template(
        "laundry/order_details.html",
        order=order,
        order_statuses=ORDER_STATUS
    )


@app.route("/laundry/subscription")
@login_required
def subscription():

    return render_template(
        "laundry/subscription.html"
    )

# ==========================================================
# ADMIN - LAUNDRY SERVICE / PRICING MANAGEMENT
# ==========================================================

@app.route("/admin/services")
@admin_required
def admin_services():

    items = ServiceItem.query.order_by(
        ServiceItem.service_type,
        ServiceItem.display_name
    ).all()

    # Group items by service_type so the template can render
    # separate sections for "pressing" and "wash_press".
    grouped_items = {}

    for item in items:
        grouped_items.setdefault(item.service_type, []).append(item)

    return render_template(
        "admin/services.html",
        grouped_items=grouped_items,
        service_types=SERVICE_TYPES
    )


@app.route("/admin/services/add", methods=["POST"])
@admin_required
def admin_add_service_item():

    service_type = request.form.get("service_type", "").strip()

    display_name = request.form.get("display_name", "").strip()

    price_string = request.form.get("price", "").strip()

    if service_type not in ("pressing", "wash_press"):
        flash("Please select a valid service type.", "danger")
        return redirect(url_for("admin_services"))

    if not display_name:
        flash("Please enter an item name.", "danger")
        return redirect(url_for("admin_services"))

    try:
        price = int(price_string)
        if price < 0:
            raise ValueError

    except (TypeError, ValueError):
        flash("Please enter a valid price.", "danger")
        return redirect(url_for("admin_services"))

    # Derive a stable internal key from the display name, e.g.
    # "Jeans / Sweatpants" -> "jeans_sweatpants"
    item_name = (
        display_name.lower()
        .replace("/", " ")
        .replace("-", " ")
    )
    item_name = "_".join(item_name.split())

    existing = ServiceItem.query.filter_by(
        service_type=service_type,
        item_name=item_name
    ).first()

    if existing:
        flash(
            f'"{display_name}" already exists under this service. '
            "Edit the existing item instead.",
            "danger"
        )
        return redirect(url_for("admin_services"))

    new_item = ServiceItem(
        service_type=service_type,
        item_name=item_name,
        display_name=display_name,
        price=price,
        is_active=True
    )

    db.session.add(new_item)
    db.session.commit()

    flash(f'"{display_name}" added successfully.', "success")

    return redirect(url_for("admin_services"))


@app.route("/admin/services/<int:item_id>/edit", methods=["POST"])
@admin_required
def admin_edit_service_item(item_id):

    item = db.get_or_404(ServiceItem, item_id)

    display_name = request.form.get("display_name", "").strip()

    price_string = request.form.get("price", "").strip()

    if not display_name:
        flash("Item name cannot be empty.", "danger")
        return redirect(url_for("admin_services"))

    try:
        price = int(price_string)
        if price < 0:
            raise ValueError

    except (TypeError, ValueError):
        flash("Please enter a valid price.", "danger")
        return redirect(url_for("admin_services"))

    item.display_name = display_name
    item.price = price

    db.session.commit()

    flash(f'"{item.display_name}" updated successfully.', "success")

    return redirect(url_for("admin_services"))


@app.route("/admin/services/<int:item_id>/toggle", methods=["POST"])
@admin_required
def admin_toggle_service_item(item_id):

    item = db.get_or_404(ServiceItem, item_id)

    item.is_active = not item.is_active

    db.session.commit()

    status = "activated" if item.is_active else "deactivated"

    flash(f'"{item.display_name}" {status}.', "success")

    return redirect(url_for("admin_services"))


@app.route("/notifications")
@login_required
def notifications():

    notifications = (
        Notification.query
        .filter_by(user_id=current_user.id)
        .order_by(Notification.created_at.desc())
        .all()
    )

    for notification in notifications:

        notification.is_read = True

    db.session.commit()

    return render_template(
        "notifications.html",
        notifications=notifications
    )

# =========================
# CREATE DATABASE
# =========================

with app.app_context():

    db.create_all()

    # One-time seed: if the service_items table is empty, populate
    # it from the LAUNDRY_PRICES dict in constants.py. After this
    # runs once, LAUNDRY_PRICES is no longer read for pricing -
    # everything after this point is managed from /admin/services.
    if ServiceItem.query.count() == 0:

        for service_type, items in LAUNDRY_PRICES.items():

            for item_name, price in items.items():

                db.session.add(ServiceItem(
                    service_type=service_type,
                    item_name=item_name,
                    display_name=item_name.replace("_", " ").title(),
                    price=price,
                    is_active=True
                ))

        db.session.commit()


# =========================
# RUN APPLICATION
# =========================

if __name__ == "__main__":

    app.run(debug=app.config["DEBUG"])