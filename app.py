from flask import Flask, render_template, redirect, url_for, flash, request
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, LaundryOrder, OrderItem
from forms import RegisterForm, LoginForm, LaundryOrderForm
from datetime import datetime, timedelta


app = Flask(__name__)


# =========================
# APP CONFIGURATION
# =========================

app.config["SECRET_KEY"] = "change-this-secret-key"

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///errandly.db"

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False


# =========================
# INITIALIZE DATABASE
# =========================

db.init_app(app)


# =========================
# INITIALIZE LOGIN MANAGER
# =========================

login_manager = LoginManager()

login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):

    return db.get_or_404(User, int(user_id))

LAUNDRY_PRICES = {
    "pressing": {
        "shirts": 150,
        "trousers": 150,
        "jeans_sweatpants": 150,
        "suits": 500,
        "uniform": 500,
        "female_wear": 350,
        "kaftan": 300,
        "jallabiya_jilbab_veil_hijab": 200,
        "kiddies_set": 150,
        "bedsheet": 500,
        "delicates": 700
    },

    "wash_press": {
        "shirts": 250,
        "trousers": 250,
        "jeans_sweatpants": 300,
        "suits_wash": 1000,
        "suits_wash_starch": 1500,
        "suits_steam": 5000,
        "uniform": 1000,
        "female_wear": 600,
        "kaftan_starch": 700,
        "kaftan_set": 500,
        "jallabiya_jilbab_veil_hijab": 400,
        "kiddies_set": 400,
        "towel": 500,
        "boxers": 200,
        "singlet": 200,
        "cap_kube": 2000,
        "cap_muhadu_a_banki": 1000,
        "stain_treatment": 1000,
        "bedsheet": 1000,
        "duvet": 2000,
        "small_carpet": 3500,
        "big_carpet": 6000,
        "delicates": 1000
    }
}
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
    return render_template("dashboard.html")

@app.route("/laundry")
@login_required
def laundry():

    return render_template("laundry/service_selection.html")



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


@app.route("/laundry/subscription")
@login_required
def subscription():

    return render_template(
        "laundry/subscription.html"
    )



# =========================
# CREATE DATABASE
# =========================

with app.app_context():

    db.create_all()


# =========================
# RUN APPLICATION
# =========================

if __name__ == "__main__":

    app.run(debug=True)