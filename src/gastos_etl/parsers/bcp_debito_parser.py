import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from bs4 import BeautifulSoup

from gastos_etl.exceptions import ParsingError
from gastos_etl.models import GastoBCP, RawEmail

# El correo real de BCP ("Realizaste un consumo") viene como una tabla HTML
# con una seccion "Datos de la operación" de pares etiqueta/valor, ej:
#
#   Total del consumo          S/ 25.00
#   Operación realizada        Consumo en establecimiento
#   Fecha y hora               30 de julio de 2026 - 06:59 PM
#   Número de Tarjeta de Débito  **** **** **** XXXX
#   Empresa                    NOMBRE DEL COMERCIO SAC
#   Número de operación        628128
#
# Deliberadamente NO se extrae el numero de tarjeta (datos de tarjeta /
# DAC): no aporta valor para trackear gastos y es informacion sensible que
# no debe persistirse.
#
# En vez de un regex fragil sobre una frase, se ancla cada valor a su
# etiqueta y se corta en la siguiente etiqueta conocida (lookahead), lo
# que es robusto sin importar si el HTML separa las celdas con
# espacios o saltos de linea al extraer el texto.
_LABELS = [
    "Total del consumo",
    "Operación realizada",
    "Fecha y hora",
    "Número de Tarjeta de Débito",
    "Número de Tarjeta de Crédito",
    "Empresa",
    "Número de operación",
]
_LABEL_ALTERNATION = "|".join(re.escape(label) for label in _LABELS)


def _field_regex(label: str) -> re.Pattern:
    return re.compile(
        rf"{re.escape(label)}\s*[:\-]?\s*(.+?)(?=(?:{_LABEL_ALTERNATION})|$)",
        re.DOTALL,
    )


_MONTO_RE = _field_regex("Total del consumo")
_FECHA_RE = _field_regex("Fecha y hora")
_EMPRESA_RE = _field_regex("Empresa")

_MONTO_VALOR_RE = re.compile(r"(S/|US\$|USD)\s*([\d,]+\.\d{2})", re.IGNORECASE)
_FECHA_VALOR_RE = re.compile(
    r"(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})\s*-\s*(\d{1,2}):(\d{2})\s*([AaPp]\.?\s?[Mm]\.?)"
)

_MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "setiembre": 9, "septiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}


class BCPDebitoParser:
    """Parser del correo "Realizaste un consumo" con tarjeta BCP (débito/crédito)."""

    def can_parse(self, raw: RawEmail) -> bool:
        sender_ok = "notificacionesbcp.com.pe" in raw.sender.lower()
        subject_ok = "consumo" in raw.subject.lower()
        return sender_ok and subject_ok

    def parse(self, raw: RawEmail) -> GastoBCP:
        text = self._extract_text(raw)

        monto_field = self._extract_field(_MONTO_RE, text, raw.message_id, "Total del consumo")
        monto_valor = _MONTO_VALOR_RE.search(monto_field)
        if not monto_valor:
            raise ParsingError(raw.message_id, f"monto invalido: {monto_field!r}")
        try:
            monto = Decimal(monto_valor.group(2).replace(",", ""))
        except InvalidOperation as exc:
            raise ParsingError(raw.message_id, f"monto invalido: {monto_valor.group(2)}") from exc
        moneda = "USD" if monto_valor.group(1).upper() in ("US$", "USD") else "PEN"

        fecha_field = self._extract_field(_FECHA_RE, text, raw.message_id, "Fecha y hora")
        fecha_consumo = self._parse_fecha_hora(fecha_field, raw.message_id)

        empresa_match = _EMPRESA_RE.search(text)
        comercio = self._clean(empresa_match.group(1)) if empresa_match else None

        return GastoBCP(
            message_id=raw.message_id,
            monto=monto,
            moneda=moneda,
            comercio=comercio,
            fecha_consumo=fecha_consumo,
        )

    @staticmethod
    def _extract_field(pattern: re.Pattern, text: str, message_id: str, label: str) -> str:
        match = pattern.search(text)
        if not match:
            raise ParsingError(message_id, f"no se encontro el campo '{label}'")
        return BCPDebitoParser._clean(match.group(1))

    @staticmethod
    def _clean(value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()

    @staticmethod
    def _parse_fecha_hora(fecha_field: str, message_id: str) -> datetime:
        match = _FECHA_VALOR_RE.search(fecha_field)
        if not match:
            raise ParsingError(message_id, f"fecha invalida: {fecha_field!r}")
        dia, mes_nombre, anio, hora, minuto, meridiano = match.groups()
        mes = _MESES.get(mes_nombre.lower())
        if mes is None:
            raise ParsingError(message_id, f"mes desconocido: {mes_nombre!r}")

        hora_i = int(hora) % 12
        if meridiano.strip().lower().startswith("p"):
            hora_i += 12

        try:
            return datetime(int(anio), mes, int(dia), hora_i, int(minuto))
        except ValueError as exc:
            raise ParsingError(message_id, f"fecha invalida: {fecha_field!r}") from exc

    @staticmethod
    def _extract_text(raw: RawEmail) -> str:
        if raw.body_html:
            soup = BeautifulSoup(raw.body_html, "html.parser")
            return soup.get_text(separator="\n", strip=True)
        return raw.body_text or ""
