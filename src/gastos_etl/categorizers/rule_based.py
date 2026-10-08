from gastos_etl.categorizers.base import GastoCategorizer

class RuleBasedCategorizer(GastoCategorizer):
    """Adaptador de categorizacion basado en reglas y palabras clave."""

    def __init__(self):
        # Mapeo simple de reglas (palabra clave -> Categoria)
        self.rules = {
            "UBER": "Transporte",
            "CABIFY": "Transporte",
            "DIDI": "Transporte",
            "LATAM": "Transporte",
            "REPSOL": "Transporte",
            "PRIMAX": "Transporte",
            "METROPOLITANO": "Transporte",
            
            "NORKYS": "Alimentacion",
            "BEMBOS": "Alimentacion",
            "MCDONALDS": "Alimentacion",
            "STARBUCKS": "Alimentacion",
            "KFC": "Alimentacion",
            "RESTAURANT": "Alimentacion",
            "CHIF": "Alimentacion",
            "CEVICH": "Alimentacion",
            
            "PLAZA VEA": "Supermercado",
            "METRO": "Supermercado",
            "TOTTUS": "Supermercado",
            "WONG": "Supermercado",
            "VIVANDA": "Supermercado",
            "MASS": "Supermercado",
            "TAMBO": "Supermercado",
            "OXXO": "Supermercado",
            
            "LUZ DEL SUR": "Servicios",
            "SEDAPAL": "Servicios",
            "CLARO": "Servicios",
            "MOVISTAR": "Servicios",
            "ENTEL": "Servicios",
            "ENEL": "Servicios",
            "CALIDDA": "Servicios",
            
            "NETFLIX": "Entretenimiento",
            "SPOTIFY": "Entretenimiento",
            "CINEPLANET": "Entretenimiento",
            "CINEMARK": "Entretenimiento",
            "STEAM": "Entretenimiento",
            
            "INKAFARMA": "Salud",
            "MIFARMA": "Salud",
            "CLINICA": "Salud",
            
            "PLIN": "Transferencia",
            "YAPE": "Transferencia",
        }

    def categorize(self, comercio: str | None) -> str:
        if not comercio:
            return "Otros"
            
        comercio_upper = comercio.upper()
        
        for keyword, category in self.rules.items():
            if keyword in comercio_upper:
                return category
                
        return "Otros"
