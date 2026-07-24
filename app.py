from flask import Flask, render_template, redirect, url_for, flash, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User
from forms import RegisterForm, LoginForm


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