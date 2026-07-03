"""Twilio (WhatsApp/SMS) + SendGrid (Email) send and inbound signature verify."""


class SendError(Exception):
    pass


class TwilioAdapter:
    def __init__(self, settings, messages_client=None, email_client=None, validator=None):
        self._s = settings
        self._messages = messages_client
        self._email = email_client
        self._validator = validator

    # -- lazy real clients (skipped when tests inject fakes) --------------
    def _messages_client(self):
        if self._messages is None:
            from twilio.rest import Client
            self._messages = Client(self._s.twilio_account_sid, self._s.twilio_auth_token).messages
        return self._messages

    def _email_client(self):
        if self._email is None:
            from sendgrid import SendGridAPIClient
            self._email = SendGridAPIClient(self._s.sendgrid_api_key)
        return self._email

    def _request_validator(self):
        if self._validator is None:
            from twilio.request_validator import RequestValidator
            self._validator = RequestValidator(self._s.twilio_auth_token)
        return self._validator

    # -- public API -------------------------------------------------------
    def send(self, channel: str, to: str, body: str, subject: str = "") -> tuple[str, str]:
        if channel == "whatsapp":
            return self._send_message(self._s.whatsapp_from, to, body)
        if channel == "sms":
            return self._send_message(self._s.sms_from, to, body)
        if channel == "email":
            return self._send_email(to, subject or "Bank Muamalat — Peringatan Pembayaran", body)
        raise SendError(f"unknown channel: {channel}")

    def _send_message(self, from_: str, to: str, body: str) -> tuple[str, str]:
        try:
            msg = self._messages_client().create(from_=from_, to=to, body=body)
            return msg.sid, msg.status
        except Exception as e:  # noqa: BLE001
            raise SendError(str(e)) from e

    def _send_email(self, to: str, subject: str, body: str) -> tuple[str, str]:
        try:
            from sendgrid.helpers.mail import Mail
            mail = Mail(
                from_email=(self._s.email_from, self._s.email_from_name),
                to_emails=to, subject=subject, plain_text_content=body,
            )
            resp = self._email_client().send(mail)
            return (resp.headers.get("X-Message-Id", "email") if hasattr(resp, "headers") else "email",
                    str(getattr(resp, "status_code", "sent")))
        except Exception as e:  # noqa: BLE001
            raise SendError(str(e)) from e

    def verify(self, url: str, params: dict, signature: str) -> bool:
        return bool(self._request_validator().validate(url, params, signature))
