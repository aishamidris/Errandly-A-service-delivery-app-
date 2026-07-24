from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, Length

from wtforms import (
    StringField,
    PasswordField,
    SubmitField
)

from wtforms.validators import (
    DataRequired,
    Email,
    Length,
    EqualTo
)


class RegisterForm(FlaskForm):

    name = StringField(
        "Full Name",
        validators=[
            DataRequired(),
            Length(min=2, max=100)
        ]
    )


    email = StringField(
        "Email Address",
        validators=[
            DataRequired(),
            Email()
        ]
    )


    phone = StringField(
        "Phone Number",
        validators=[
            DataRequired(),
            Length(min=10, max=20)
        ]
    )


    address = StringField(
        "Address",
        validators=[
            DataRequired(),
            Length(min=5, max=250)
        ]
    )


    password = PasswordField(
        "Password",
        validators=[
            DataRequired(),
            Length(min=8)
        ]
    )


    confirm_password = PasswordField(
        "Confirm Password",
        validators=[
            DataRequired(),
            EqualTo(
                "password",
                message="Passwords must match."
            )
        ]
    )


    submit = SubmitField(
        "Create Account"
    )

    from wtforms.validators import DataRequired, Email, Length


class LoginForm(FlaskForm):
    email = StringField(
        "Email",
        validators=[DataRequired(), Email()]
    )

    password = PasswordField(
        "Password",
        validators=[DataRequired(), Length(min=8)]
    )

    submit = SubmitField("Login")