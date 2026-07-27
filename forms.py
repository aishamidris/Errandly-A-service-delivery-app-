from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField, IntegerField, DateField
from wtforms.validators import DataRequired, Email, Length,NumberRange, EqualTo






class RegisterForm(FlaskForm):

    name = StringField("Full Name", validators=[DataRequired(),Length(min=2, max=100)])
    email = StringField("Email Address", validators=[DataRequired(), Email()])
    phone = StringField("Phone Number", validators=[DataRequired(), Length(min=10, max=20)])
    address = StringField("Address", validators=[DataRequired(), Length(min=5, max=250)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField("Confirm Password", validators=[DataRequired(), EqualTo("password", message="Passwords must match.")])
    submit = SubmitField("Create Account")


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=8)])
    submit = SubmitField("Login")


class LaundryOrderForm(FlaskForm):

    service_type = SelectField("Service Type", choices=[("pressing", "Pressing Only"), ("wash_press", "Wash & Press")],validators=[DataRequired()])
    shirts = IntegerField("Shirts", default=0, validators=[NumberRange(min=0)])
    trousers = IntegerField("Trousers", default=0, validators=[NumberRange(min=0)])
    jeans_sweatpants = IntegerField("Jeans / Sweatpants", default=0, validators=[NumberRange(min=0)])
    suits_wash = IntegerField("Suits - wash", default=0, validators=[NumberRange(min=0)])
    suits_wash_starch = IntegerField("Suits - wash & starch", default=0, validators=[NumberRange(min=0)])
    suits_steam = IntegerField("Suits - steam", default=0, validators=[NumberRange(min=0)])
    uniform = IntegerField("Uniform", default=0, validators=[NumberRange(min=0)])
    female_wear = IntegerField("Female Wear", default=0, validators=[NumberRange(min=0)])
    kaftan_starch = IntegerField("Kaftan - starch", default=0,validators=[NumberRange(min=0)])
    kaftan_set = IntegerField("Kaftan - set", default=0, validators=[NumberRange(min=0)])
    jallabiya_jilbab_veil_hijab = IntegerField("Jallabiya / Jilbab / Veil / Hijab", default=0, validators=[NumberRange(min=0)])
    kiddies_set = IntegerField("Kiddies Set", default=0, validators=[NumberRange(min=0)])
    towel = IntegerField("Towel", default=0, validators=[NumberRange(min=0)])
    boxers = IntegerField("Boxers", default=0, validators=[NumberRange(min=0)])
    singlet = IntegerField("Singlet", default=0, validators=[NumberRange(min=0)])
    cap_kube = IntegerField("Cap - Kube", default=0, validators=[NumberRange(min=0)])
    cap_muhadu_a_banki = IntegerField("Cap - Muhadu / A Banki", default=0, validators=[NumberRange(min=0)])
    stain_treatment = IntegerField("Stain Treatment", default=0, validators=[NumberRange(min=0)])
    bedsheet = IntegerField("Bedsheet", default=0, validators=[NumberRange(min=0)])
    duvet = IntegerField("Duvet", default=0, validators=[NumberRange(min=0)])
    small_carpet = IntegerField("Small Carpet", default=0, validators=[NumberRange(min=0)])
    big_carpet = IntegerField("Big Carpet", default=0, validators=[NumberRange  (min=0)])
    delicates = IntegerField("Delicates", default=0, validators=[NumberRange(min=0)])
    pickup_date = DateField("Pickup Date", format="%Y-%m-%d", validators=[DataRequired()])
    submit = SubmitField("Continue")