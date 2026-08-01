import email
import imaplib
import logging
from datetime import datetime
from email.header import decode_header
from email.utils import parsedate_to_datetime

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from gastos_etl.exceptions import MailboxConnectionError
from gastos_etl.models import RawEmail

logger = logging.getLogger(__name__)


def _decode(value: str | None) -> str:
    if not value:
        return ""
    parts = decode_header(value)
    return "".join(
        chunk.decode(enc or "utf-8", errors="replace") if isinstance(chunk, bytes) else chunk
        for chunk, enc in parts
    )


def _build_subject_clause(subject_hints: list[str]) -> str:
    """Arma una clausula IMAP `OR SUBJECT "a" SUBJECT "b" ...` anidada.

    IMAP SEARCH solo soporta OR binario (2 criterios), por eso mas de 2
    asuntos requieren anidar: `OR SUBJECT "a" OR SUBJECT "b" SUBJECT "c"`.
    """
    if len(subject_hints) == 1:
        return f'SUBJECT "{subject_hints[0]}"'
    clause = f'SUBJECT "{subject_hints[-1]}"'
    for hint in reversed(subject_hints[:-1]):
        clause = f'OR SUBJECT "{hint}" {clause}'
    return clause


class ImapEmailSource:
    """Implementación de EmailSource sobre IMAP con App Password.

    No usa OAuth: basta un usuario + contraseña de aplicación de Google
    (requiere 2FA habilitado en la cuenta). El "marcado como procesado"
    se hace agregando un label (Gmail expone labels como carpetas IMAP)
    en vez de usar flags IMAP estándar, porque persiste igual que en la
    web de Gmail y es visualmente auditable.
    """

    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        app_password: str,
        mailbox: str,
        sender_filter: str,
        subject_hints: list[str],
        processed_label: str,
    ):
        self._host = host
        self._port = port
        self._user = user
        self._password = app_password
        self._mailbox = mailbox
        self._sender_filter = sender_filter
        self._subject_hints = subject_hints
        self._processed_label = processed_label

    @retry(
        retry=retry_if_exception_type((imaplib.IMAP4.error, OSError)),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(4),
        reraise=True,
    )
    def _connect(self) -> imaplib.IMAP4_SSL:
        try:
            conn = imaplib.IMAP4_SSL(self._host, self._port)
            conn.login(self._user, self._password)
            return conn
        except (imaplib.IMAP4.error, OSError) as exc:
            raise MailboxConnectionError(str(exc)) from exc

    def _ensure_label_exists(self, conn: imaplib.IMAP4_SSL) -> None:
        status, _ = conn.select(f'"{self._processed_label}"', readonly=True)
        if status != "OK":
            conn.create(f'"{self._processed_label}"')

    def fetch_unprocessed(self, since: datetime) -> list[RawEmail]:
        conn = self._connect()
        try:
            self._ensure_label_exists(conn)
            conn.select(f'"{self._mailbox}"')

            date_str = since.strftime("%d-%b-%Y")
            subject_clause = _build_subject_clause(self._subject_hints)
            criteria = (
                f'(FROM "{self._sender_filter}" '
                f"{subject_clause} "
                f'SINCE "{date_str}" '
                f'NOT KEYWORD "{self._processed_label}")'
            )
            status, data = conn.search(None, criteria)
            if status != "OK":
                logger.warning("Busqueda IMAP fallo con status=%s", status)
                return []

            emails: list[RawEmail] = []
            for num in data[0].split():
                status, msg_data = conn.fetch(num, "(RFC822)")
                if status != "OK" or not msg_data or not msg_data[0]:
                    continue
                raw_bytes = msg_data[0][1]
                emails.append(self._to_raw_email(raw_bytes))
            return emails
        finally:
            conn.logout()

    def mark_processed(self, message_id: str) -> None:
        conn = self._connect()
        try:
            conn.select(f'"{self._mailbox}"')
            status, data = conn.search(None, f'(HEADER Message-ID "{message_id}")')
            if status == "OK" and data[0]:
                num = data[0].split()[0]
                conn.copy(num, f'"{self._processed_label}"')
                conn.store(num, "+FLAGS", f'"{self._processed_label}"')
        finally:
            conn.logout()

    @staticmethod
    def _to_raw_email(raw_bytes: bytes) -> RawEmail:
        msg = email.message_from_bytes(raw_bytes)
        message_id = _decode(msg.get("Message-ID")).strip() or msg.get("Message-ID", "")
        subject = _decode(msg.get("Subject"))
        sender = _decode(msg.get("From"))
        try:
            received_at = parsedate_to_datetime(msg.get("Date"))
        except (TypeError, ValueError):
            received_at = datetime.utcnow()

        body_html, body_text = None, None
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                disposition = str(part.get("Content-Disposition", ""))
                if "attachment" in disposition:
                    continue
                payload = part.get_payload(decode=True)
                if payload is None:
                    continue
                charset = part.get_content_charset() or "utf-8"
                text = payload.decode(charset, errors="replace")
                if content_type == "text/html":
                    body_html = text
                elif content_type == "text/plain":
                    body_text = text
        else:
            payload = msg.get_payload(decode=True)
            if payload is not None:
                charset = msg.get_content_charset() or "utf-8"
                text = payload.decode(charset, errors="replace")
                if msg.get_content_type() == "text/html":
                    body_html = text
                else:
                    body_text = text

        return RawEmail(
            message_id=message_id,
            subject=subject,
            sender=sender,
            received_at=received_at,
            body_html=body_html,
            body_text=body_text,
        )
