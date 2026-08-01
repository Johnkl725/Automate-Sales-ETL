class GastoETLError(Exception):
    """Base de todas las excepciones del dominio."""


class ParsingError(GastoETLError):
    """El formato del correo no coincide con lo que el parser espera.

    No debe tumbar el pipeline entero: se loguea el mensaje afectado
    y se continúa con el resto del batch.
    """

    def __init__(self, message_id: str, reason: str):
        self.message_id = message_id
        self.reason = reason
        super().__init__(f"[{message_id}] {reason}")


class NoParserAvailableError(GastoETLError):
    """Ningún EmailParser registrado supo procesar el correo."""

    def __init__(self, message_id: str):
        self.message_id = message_id
        super().__init__(f"No hay parser para el correo {message_id}")


class MailboxConnectionError(GastoETLError):
    """Fallo de red/autenticación al hablar con el servidor IMAP."""
