from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class RawEmail(BaseModel):
    """Correo crudo tal como llega de IMAP, ya decodificado a texto."""

    message_id: str
    subject: str
    sender: str
    received_at: datetime
    body_html: str | None = None
    body_text: str | None = None


class GastoBCP(BaseModel):
    """Hecho normalizado listo para persistir.

    Deliberadamente NO incluye ningun dato de tarjeta (numero completo,
    ultimos digitos, tipo de tarjeta, etc.) -- no aporta valor para
    trackear gastos y es informacion sensible que no debe persistirse.
    """

    message_id: str
    monto: Decimal = Field(gt=0)
    moneda: str = "PEN"
    tipo: str = "consumo_tarjeta"  # o "pago_servicio"
    comercio: str | None = None
    fecha_consumo: datetime
    procesado_en: datetime = Field(default_factory=datetime.utcnow)
