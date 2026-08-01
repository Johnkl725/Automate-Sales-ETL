import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from bs4 import BeautifulSoup

from gastos_etl.exceptions import ParsingError
from gastos_etl.models import GastoBCP, RawEmail

# Correo "ENVIO AUTOMATICO - CONSTANCIA DE PAGO DE SERVICIO - BANCA MOVIL BCP".
# NOTA: calibrado sin un .eml real de este tipo (a diferencia del parser de
# consumo con tarjeta). Ajustar estos regex en cuanto tengamos un ejemplo
# real -- especialmente si "Empresa"/"Monto total" vienen en celdas de tabla
# separadas (como en el correo de consumo) en vez de "Etiqueta: valor" en la
# misma linea.
_EMPRESA_RE = re.compile(r"Empresa\s*:?\s*\n?\s*([^\n]{2,80})", re.IGNORECASE)
_MONTO_TOTAL_RE = re.compile(
    r"Monto\s+total\s*:?\s*\n?\s*(S/|US\$|USD)?\s*([\d,]+\.\d{2})", re.IGNORECASE
)
_FECHA_VALOR_RE = re.compile(
    r"(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})\s*-\s*(\d{1,2}):(\d{2})\s*([AaPp]\.?\s?[Mm]\.?)"
)

_MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "setiembre": 9, "septiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}

_SUBJECT_HINT = "constancia de pago de servicio"


class BCPPagoServicioParser:
    """Parser del correo "Constancia de pago de servicio" (Banca Móvil BCP)."""

    def can_parse(self, raw: RawEmail) -> bool:
        sender_ok = "notificacionesbcp.com.pe" in raw.sender.lower()
        subject_ok = _SUBJECT_HINT in raw.subject.lower()
        return sender_ok and subject_ok

    def parse(self, raw: RawEmail) -> GastoBCP:
        text = self._extract_text(raw)

        empresa_match = _EMPRESA_RE.search(text)
        if not empresa_match:
            raise ParsingError(raw.message_id, "no se encontro el campo 'Empresa'")
        comercio = self._clean(empresa_match.group(1))

        monto_match = _MONTO_TOTAL_RE.search(text)
        if not monto_match:
            raise ParsingError(raw.message_id, "no se encontro el campo 'Monto total'")
        try:
            monto = Decimal(monto_match.group(2).replace(",", ""))
        except InvalidOperation as exc:
            raise ParsingError(raw.message_id, f"monto invalido: {monto_match.group(2)}") from exc
        moneda = "USD" if (monto_match.group(1) or "").upper() in ("US$", "USD") else "PEN"

        fecha_consumo = self._parse_fecha_opcional(text) or raw.received_at

        return GastoBCP(
            message_id=raw.message_id,
            monto=monto,
            moneda=moneda,
            tipo="pago_servicio",
            comercio=comercio,
            fecha_consumo=fecha_consumo,
        )

    @staticmethod
    def _parse_fecha_opcional(text: str) -> datetime | None:
        match = _FECHA_VALOR_RE.search(text)
        if not match:
            return None
        dia, mes_nombre, anio, hora, minuto, meridiano = match.groups()
        mes = _MESES.get(mes_nombre.lower())
        if mes is None:
            return None
        hora_i = int(hora) % 12
        if meridiano.strip().lower().startswith("p"):
            hora_i += 12
        try:
            return datetime(int(anio), mes, int(dia), hora_i, int(minuto))
        except ValueError:
            return None

    @staticmethod
    def _clean(value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()

    @staticmethod
    def _extract_text(raw: RawEmail) -> str:
        if raw.body_html:
            soup = BeautifulSoup(raw.body_html, "html.parser")
            return soup.get_text(separator="\n", strip=True)
        return raw.body_text or ""
