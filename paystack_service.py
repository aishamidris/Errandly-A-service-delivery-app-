"""
paystack_service.py

Handles Paystack transaction initialization and verification.
Uses the `requests` library to talk to Paystack's REST API directly
(no SDK needed - Paystack's API is simple enough that a dependency
isn't worth it).
"""

import hashlib
import hmac
import uuid
import requests
from flask import current_app


PAYSTACK_INITIALIZE_URL = "https://api.paystack.co/transaction/initialize"
PAYSTACK_VERIFY_URL = "https://api.paystack.co/transaction/verify/{}"

# Paystack requires amounts in kobo (the smallest currency unit),
# not naira. 1 naira = 100 kobo.
KOBO_PER_NAIRA = 100


class PaystackError(Exception):
    """Raised when Paystack rejects a request or is unreachable."""
    pass


def _headers():
    secret_key = current_app.config.get("PAYSTACK_SECRET_KEY")

    if not secret_key:
        raise PaystackError(
            "PAYSTACK_SECRET_KEY is not set. Add it to your .env file."
        )

    return {
        "Authorization": f"Bearer {secret_key}",
        "Content-Type": "application/json",
    }


def generate_reference(order_id):
    """
    Builds a unique reference for this payment attempt. Includes the
    order id for easy manual lookup in the Paystack dashboard, plus a
    random suffix so retries after a failed payment get a fresh
    reference (Paystack rejects a second initialize on a reused one
    that already succeeded).
    """
    return f"errandly-order-{order_id}-{uuid.uuid4().hex[:10]}"


def initialize_transaction(order, callback_url):
    """
    Starts a Paystack transaction for the given LaundryOrder.
    Returns (authorization_url, reference) on success.
    Raises PaystackError on failure.
    """

    amount_naira = order.verified_total or order.submitted_total

    if not amount_naira or amount_naira <= 0:
        raise PaystackError(
            "This order has no amount to charge. "
            "It may not have been verified yet."
        )

    reference = generate_reference(order.id)

    payload = {
        "email": order.user.email,
        "amount": amount_naira * KOBO_PER_NAIRA,
        "reference": reference,
        "callback_url": callback_url,
        "metadata": {
            "order_id": order.id,
            "customer_name": order.user.name,
        },
    }

    try:
        response = requests.post(
            PAYSTACK_INITIALIZE_URL,
            json=payload,
            headers=_headers(),
            timeout=15,
        )

    except requests.exceptions.RequestException as e:
        raise PaystackError(f"Could not reach Paystack: {e}")

    data = response.json()

    if not response.ok or not data.get("status"):
        message = data.get("message", "Payment initialization failed.")
        raise PaystackError(message)

    authorization_url = data["data"]["authorization_url"]

    return authorization_url, reference


def verify_transaction(reference):
    """
    Verifies a transaction by reference with Paystack.
    Returns the transaction data dict on success (status == "success").
    Raises PaystackError if verification fails, the transaction wasn't
    successful, or Paystack is unreachable.
    """

    try:
        response = requests.get(
            PAYSTACK_VERIFY_URL.format(reference),
            headers=_headers(),
            timeout=15,
        )

    except requests.exceptions.RequestException as e:
        raise PaystackError(f"Could not reach Paystack: {e}")

    data = response.json()

    if not response.ok or not data.get("status"):
        message = data.get("message", "Payment verification failed.")
        raise PaystackError(message)

    transaction = data["data"]

    if transaction.get("status") != "success":
        raise PaystackError(
            f"Payment was not successful "
            f"(status: {transaction.get('status')})."
        )

    return transaction


def verify_webhook_signature(request_body, signature_header):
    """
    Confirms a webhook request actually came from Paystack, not
    someone POSTing a fake "charge.success" event to mark an order
    paid for free.

    Paystack signs the raw request body with your secret key
    (HMAC-SHA512) and sends the result in the x-paystack-signature
    header. We recompute it locally and compare.

    request_body must be the raw bytes of the request, exactly as
    received - re-serializing parsed JSON can produce different
    bytes (key order, whitespace) and silently break verification.
    """

    secret_key = current_app.config.get("PAYSTACK_SECRET_KEY")

    if not secret_key or not signature_header:
        return False

    expected_signature = hmac.new(
        secret_key.encode("utf-8"),
        request_body,
        hashlib.sha512
    ).hexdigest()

    # constant-time comparison - a plain == leaks timing information
    # that could theoretically help forge a valid signature.
    return hmac.compare_digest(expected_signature, signature_header)
