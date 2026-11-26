"""Send a short text message. Providers: "console" (local demo) and "twilio"."""

import logging

import httpx

from app.core.config import get_settings

log = logging.getLogger("healthspeak.sms")


class SmsNotSent(Exception):
    """Delivery was not possible (not configured, refused, or provider error)."""


def send_sms(phone: str, text: str) -> None:
    s = get_settings()
    provider = s.sms_provider.lower()
    if provider == "console":
        if s.app_env.lower() == "production":
            raise SmsNotSent("The console SMS provider is for local demos and is disabled in production.")
        # Local demo only: shows the message in the API window instead of sending it.
        print(f"\n[LOCAL DEMO SMS - not really sent] to {phone}: {text}\n", flush=True)
        return
    if provider == "twilio":
        if not (s.twilio_account_sid and s.twilio_auth_token and s.twilio_from_number):
            raise SmsNotSent("Twilio is not fully configured.")
        try:
            r = httpx.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{s.twilio_account_sid}/Messages.json",
                auth=(s.twilio_account_sid, s.twilio_auth_token),
                data={"To": phone, "From": s.twilio_from_number, "Body": text},
                timeout=10,
            )
        except httpx.HTTPError as e:
            raise SmsNotSent(f"SMS provider unreachable: {type(e).__name__}") from None
        if r.status_code >= 300:
            raise SmsNotSent(f"SMS provider refused the message (HTTP {r.status_code}).")
        return
    raise SmsNotSent(f"Unknown SMS_PROVIDER {s.sms_provider!r}.")
