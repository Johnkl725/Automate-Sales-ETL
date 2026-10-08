from gastos_etl.categorizers.rule_based import RuleBasedCategorizer

def test_rule_based_categorizer():
    categorizer = RuleBasedCategorizer()
    
    assert categorizer.categorize("UBER EATS") == "Transporte"
    assert categorizer.categorize("CABIFY PERU") == "Transporte"
    assert categorizer.categorize("POLLERIA NORKYS SAC") == "Alimentacion"
    assert categorizer.categorize("SUPERMERCADOS PERUANOS PLAZA VEA") == "Supermercado"
    assert categorizer.categorize("PAGO SERVICIO LUZ DEL SUR") == "Servicios"
    assert categorizer.categorize("NETFLIX.COM") == "Entretenimiento"
    assert categorizer.categorize("TIENDA DESCONOCIDA") == "Otros"
    assert categorizer.categorize(None) == "Otros"
