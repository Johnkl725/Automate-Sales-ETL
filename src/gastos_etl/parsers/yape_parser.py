import re
from datetime import datetime

from bs4 import BeautifulSoup

from gastos_etl.exceptions import ParsingError
from gastos_etl.models import GastoBCP, RawEmail
from gastos_etl.parsers.base import EmailParser

_MONTO_RE = re.compile(r"S/\s*([\d,]+\.\d{2})")
_FECHA_RE = re.compile(r"Fecha:\s*(.+)")

# Mapeo simple para los meses en Yape (ej. "oct.")
_MESES_YAPE = {
    "ene.": "01",
    "feb.": "02",
    "mar.": "03",
    "abr.": "04",
    "may.": "05",
    "jun.": "06",
    "jul.": "07",
    "ago.": "08",
    "sep.": "09",
    "set.": "09",
    "oct.": "10",
    "nov.": "11",
    "dic.": "12",
}

class YapeParser(EmailParser):
    """Estrategia para parsear notificaciones de Yape ('Yapeaste exitosamente')."""

    def can_parse(self, raw: RawEmail) -> bool:
        # A veces el asunto es "Yape! Pagaste S/..." o contiene "Yapeaste"
        subject = raw.subject.lower()
        return "yape" in subject or "yapeaste" in subject

    def parse(self, raw: RawEmail) -> GastoBCP:
        html = raw.body_html or raw.body_text or ""
        soup = BeautifulSoup(html, "html.parser")
        text_content = soup.get_text(separator=" ", strip=True)

        # Monto
        monto_match = _MONTO_RE.search(text_content)
        if not monto_match:
            raise ParsingError(raw.message_id, "No se encontro monto de Yape")
        monto_str = monto_match.group(1).replace(",", "")

        # Destinatario (Comercio / Persona)
        # Buscar el nombre despues de "Le yapeaste a"
        destinatario = None
        match_dest = re.search(r"Le yapeaste a\s+(.+?)(?=\s+Monto)", text_content, re.IGNORECASE)
        if match_dest:
            destinatario = match_dest.group(1).strip()
        else:
            destinatario = "Yape Destinatario Desconocido"

        # Fecha (Fallback a fecha del correo si falla el parseo especifico)
        fecha_consumo = raw.received_at
        match_fecha = _FECHA_RE.search(text_content)
        if match_fecha:
            raw_fecha = match_fecha.group(1).strip()
            # Intento basico de parseo de fecha yape (12 de oct. de 2026 - 12:30 PM)
            try:
                # Normalizamos la fecha reemplazando el mes por su numero
                normalized_date = raw_fecha.lower()
                for mes_str, mes_num in _MESES_YAPE.items():
                    normalized_date = normalized_date.replace(f" de {mes_str} de ", f"/{mes_num}/")
                    normalized_date = normalized_date.replace(f" {mes_str} ", f"/{mes_num}/")
                
                # Se asume formato "08/10/2026 - 12:30 pm" 
                # Hacemos un regex para limpiar todo
                clean_fecha_match = re.search(r"(\d{1,2}/\d{2}/\d{4})\s*-\s*(\d{1,2}:\d{2}\s*[ap]m)", normalized_date)
                if clean_fecha_match:
                    fecha_str = f"{clean_fecha_match.group(1)} {clean_fecha_match.group(2)}"
                    fecha_consumo = datetime.strptime(fecha_str, "%d/%m/%Y %I:%M %pm")
            except Exception:
                pass # Fallback a received_at

        return GastoBCP(
            message_id=raw.message_id,
            monto=monto_str,
            tipo="yape",
            comercio=destinatario,
            fecha_consumo=fecha_consumo,
        )
