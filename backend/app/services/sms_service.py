"""Send a short text message. Providers: "console" (local demo) and "twilio".

`status()` says whether delivery is possible at all, so callers can tell the user the truth
instead of pretending a message was sent.
"""

import logging
from dataclasses import dataclass

import httpx

from app.core.config import get_settings

log = logging.getLogger("healthspeak.sms")


class SmsNotSent(Exception):
    """Delivery was not possible (not configured, refused, or provider error)."""


@dataclass(frozen=True)
class SmsStatus:
    ready: bool
    provider: str
    dev_mode: bool  # console provider outside production: codes are printed, not sent
    reason: str | None = None


def status() -> SmsStatus:
    s = get_settings()
    provider = s.sms_provider.lower()
    if provider == "console":
        if s.app_env.lower() == "production":
            return SmsStatus(False, provider, False,
                             "SMS is not configured. The console provider is disabled in production.")
        return SmsStatus(True, provider, True)
    if provider == "twilio":
        if not (s.twilio_account_sid and s.twilio_auth_token and s.twilio_from_number):
            return SmsStatus(False, provider, False, "Twilio is selected but its settings are incomplete.")
        return SmsStatus(True, provider, False)
    return SmsStatus(False, provider, False, f"Unknown SMS_PROVIDER {s.sms_provider!r}.")


def dev_echo_allowed() -> bool:
    """May the one-time code be returned to the browser? Development + console provider ONLY."""
    s = get_settings()
    return (s.app_env.lower() == "development" and s.sms_provider.lower() == "console"
            and s.dev_otp_echo is not False)


def send_sms(phone: str, text: str) -> None:
    st = status()
    if not st.ready:
        raise SmsNotSent(st.reason or "SMS is not available.")
    s = get_settings()
    if st.provider == "console":
        # Local demo only: shows the message in the API window instead of sending it.
        print(f"\n[LOCAL DEMO SMS - not really sent] to {phone}: {text}\n", flush=True)
        return
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
