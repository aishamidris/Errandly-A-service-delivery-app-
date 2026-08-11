"""
sms_service.py

Sends SMS and WhatsApp notifications to customers via Twilio.
Designed to fail silently (log only) so a notification failure
never breaks the customer-facing request that triggered it.
"""

import os
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException


TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")

# Regular SMS-capable Twilio number, e.g. "+15017122661"
TWILIO_SMS_FROM = os.environ.get("TWILIO_SMS_FROM")

# WhatsApp sender - sandbox default is Twilio's shared sandbox number.
# Once you get a production WhatsApp sender approved, update this env var.
TWILIO_WHATSAPP_FROM = os.environ.get(
    "TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886"
)

_client = None


def _get_client():
    """Lazily create the Twilio client so importing this module never
    fails just because env vars aren't set yet (e.g. during local dev)."""
    global _client

    if _client is None:
        if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
            return None
        _client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

    return _client


def format_nigerian_number(phone):
    """
    Converts a locally-formatted Nigerian number (e.g. "08012345678")
    into E.164 format (e.g. "+2348012345678"), which Twilio requires.
    Leaves already-international numbers untouched.
    """
    phone = phone.strip().replace(" ", "").replace("-", "")

    if phone.startswith("+"):
        return phone

    if phone.startswith("0"):
        return "+234" + phone[1:]

    if phone.startswith("234"):
        return "+" + phone

    # Fallback: assume it's missing the country code entirely
    return "+234" + phone


def send_sms(to_phone, message):
    """Sends a plain SMS. Returns True on success, False otherwise."""
    client = _get_client()

    if client is None or not TWILIO_SMS_FROM:
        print(f"[sms disabled] Would have sent SMS to {to_phone}: {message}")
        return False

    try:
        client.messages.create(
            body=message,
            from_=TWILIO_SMS_FROM,
            to=format_nigerian_number(to_phone),
        )
        return True

    except TwilioRestException as e:
        print(f"[sms error] Failed to send SMS to {to_phone}: {e}")
        return False


def send_whatsapp(to_phone, message):
    """Sends a WhatsApp message. Returns True on success, False otherwise."""
    client = _get_client()

    if client is None:
        print(f"[whatsapp disabled] Would have sent WhatsApp to {to_phone}: {message}")
        return False

    try:
        client.messages.create(
            body=message,
            from_=TWILIO_WHATSAPP_FROM,
            to="whatsapp:" + format_nigerian_number(to_phone),
        )
        return True

    except TwilioRestException as e:
        print(f"[whatsapp error] Failed to send WhatsApp to {to_phone}: {e}")
        return False


def notify_customer(user, message, sms=True, whatsapp=True):
    """
    Sends the same message to a customer over SMS and/or WhatsApp.
    `user` must have a `.phone` attribute (your User model already does).
    Call this alongside create_notification() for the in-app copy.
    """
    results = {}

    if sms:
        results["sms"] = send_sms(user.phone, message)

    if whatsapp:
        results["whatsapp"] = send_whatsapp(user.phone, message)

    return results