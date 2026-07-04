"""Twilio (WhatsApp/SMS) + SMTP (Email) send and inbound signature verify."""


class SendError(Exception):
    pass


class TwilioAdapter:
    def __init__(self, settings, messages_client=None, smtp_sender=None, validator=None):
        self._s = settings
        self._messages = messages_client
        self._smtp_sender = smtp_sender
        self._validator = validator

    # -- lazy real clients (skipped when tests inject fakes) --------------
    def _messages_client(self):
        if self._messages is None:
            from twilio.rest import Client
            self._messages = Client(self._s.twilio_account_sid, self._s.twilio_auth_token).messages
        return self._messages

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
            from email.message import EmailMessage
            msg = EmailMessage()
            msg["From"] = f"{self._s.email_from_name} <{self._s.email_from}>"
            msg["To"] = to
            msg["Subject"] = subject
            msg.set_content(body)
            sender = self._smtp_sender or self._default_smtp_send
            sender(msg)
            return ("email", "sent")
        except Exception as e:  # noqa: BLE001
            raise SendError(str(e)) from e

    def _default_smtp_send(self, msg) -> None:
        import smtplib  # lazy stdlib
        with smtplib.SMTP(self._s.smtp_host, self._s.smtp_port) as server:
            if self._s.smtp_starttls:
                server.starttls()
            if self._s.smtp_user:
                server.login(self._s.smtp_user, self._s.smtp_password)
            server.send_message(msg)

    def verify(self, url: str, params: dict, signature: str) -> bool:
        return bool(self._request_validator().validate(url, params, signature))
