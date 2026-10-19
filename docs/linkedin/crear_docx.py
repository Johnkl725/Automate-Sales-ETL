from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZipFile, ZIP_DEFLATED
import xml.etree.ElementTree as ET

OUT = Path(__file__).resolve().parent
POST = [
    'Convertí mis notificaciones de gastos en un proyecto de ingeniería de datos.',
    'Así nació Gastos ETL: un proyecto personal para transformar correos de operaciones financieras en datos estructurados y analizables.',
    'El flujo comienza con la extracción de notificaciones por IMAP. Con Python, proceso correos de consumos con tarjeta BCP, pagos de servicios y transferencias Yape, extraigo sus campos y clasifico los comercios mediante reglas.',
    'Los datos se almacenan en SQL Server con un modelo estrella: una tabla de hechos de gastos y dimensiones de tiempo, tipo de operación y comercio. Apache Airflow programa la ejecución diaria e incorpora reintentos y notificaciones por correo.',
    'Detrás del flujo hay decisiones que considero clave:',
    '• Arquitectura hexagonal para separar la lógica del negocio de las fuentes de datos y la persistencia.',
    '• Control por identificador de correo para evitar volver a cargar el mismo mensaje.',
    '• Manejo de errores de parsing por mensaje, para continuar con los demás correos del lote.',
    '• Pruebas unitarias con Pytest y un flujo de integración continua en GitHub Actions.',
    'El proyecto también cuenta con un reporte en Power BI para analizar mis gastos. Lo mantengo privado porque contiene información financiera personal; aquí comparto el proceso técnico y las decisiones de diseño.',
    'Este proyecto me permitió conectar extracción, transformación, modelado dimensional y visualización en un caso de uso propio. El aprendizaje más valioso: la calidad del análisis empieza mucho antes de construir el reporte.',
    '¿Has convertido alguna necesidad cotidiana en un proyecto de datos? Me gustaría conocer tu experiencia.',
    '#DataEngineering #Python #SQLServer #ApacheAirflow #PowerBI',
]

def p(text, style=None):
    props = f'<w:pStyle w:val="{style}"/>' if style else ''
    return f'<w:p><w:pPr>{props}</w:pPr><w:r><w:t xml:space="preserve">{escape(text)}</w:t></w:r></w:p>'

body = p('Gastos ETL | Publicación para LinkedIn', 'Title')
body += p('Texto listo para copiar', 'Subtitle')
body += ''.join(p(t) for t in POST)
body += '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'
body += p('Notas de revisión del proyecto', 'Title')
body += p('Material de apoyo · No forma parte de la publicación', 'Subtitle')
for heading, text in [
    ('Enfoque de la publicación', 'Presentar un caso personal de ingeniería de datos, desde correos hasta información analítica. La existencia del reporte en Power BI se incorpora según tu confirmación; no se atribuyen métricas, visuales ni configuraciones de actualización que no se hayan revisado.'),
    ('Qué respalda el código', 'El pipeline usa interfaces para fuente, parsers, repositorio y categorización. El DAG incluye parsers de BCP y Yape, SQL Server y ejecución diaria a las 08:00 de Lima. El repositorio define fact_gastos, dim_tiempo, dim_tipo y dim_comercio, con una restricción única por message_id. Existen pruebas y un workflow de CI con Pytest; no se ejecutaron para esta revisión editorial.'),
    ('Diferencias frente al README', 'El README habla de tiempo real, pero el DAG configura procesamiento diario por lotes. La clasificación implementada usa reglas y palabras clave, no IA. El control de duplicados se aplica al identificador del correo: no prueba que una operación notificada en mensajes distintos se deduplique. Por eso el texto evita garantías absolutas de calidad o preparación para producción.'),
    ('API y dashboard web', 'Hay una API NestJS y un dashboard React/Vite. La API revisada utiliza DuckDB mediante DuckdbService, aunque el README la presenta dentro del flujo con SQL Server. Se omite esa conexión de la publicación para no afirmar una integración que el código actual no refleja.'),
    ('Cómo acompañar el texto', 'Puedes acompañarlo con un diagrama de la arquitectura o del modelo estrella, sin filas de datos. El reporte real de Power BI permanece privado. Si preparas una demostración visual más adelante, usa datos completamente ficticios e identifícala como demostración.'),
    ('Archivos revisados', 'README.md; src/gastos_etl/pipeline.py; src/gastos_etl/categorizers/rule_based.py; src/gastos_etl/repositories/sqlserver_repository.py; dags/gastos_bcp_dag.py; api/src/gastos/gastos.service.ts; api/src/gastos/duckdb.service.ts; .github/workflows/ci.yml; tests/test_pipeline.py; tests/test_sqlserver_repository.py.'),
]:
    body += p(heading, 'Heading1') + p(text)

ns = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
document = f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="{ns}"><w:body>{body}<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="850" w:right="1000" w:bottom="850" w:left="1000"/></w:sectPr></w:body></w:document>'
styles = f'''<?xml version="1.0" encoding="UTF-8"?><w:styles xmlns:w="{ns}">
<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:sz w:val="22"/><w:color w:val="253247"/><w:lang w:val="es-PE"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:spacing w:after="120" w:line="260" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:pPr><w:keepNext/><w:spacing w:after="120"/></w:pPr><w:rPr><w:b/><w:color w:val="145A75"/><w:sz w:val="34"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Subtitle"><w:name w:val="Subtitle"/><w:pPr><w:keepNext/><w:spacing w:after="240"/></w:pPr><w:rPr><w:color w:val="63758A"/><w:sz w:val="20"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:pPr><w:keepNext/><w:spacing w:before="160" w:after="70"/></w:pPr><w:rPr><w:b/><w:color w:val="145A75"/><w:sz w:val="24"/></w:rPr></w:style></w:styles>'''
parts = {
    '[Content_Types].xml': '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/></Types>',
    '_rels/.rels': '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>',
    'word/_rels/document.xml.rels': '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>',
    'word/document.xml': document,
    'word/styles.xml': styles,
}
target = OUT / 'Publicacion_LinkedIn_Gastos_ETL.docx'
with ZipFile(target, 'w', ZIP_DEFLATED) as z:
    for name, content in parts.items():
        ET.fromstring(content)
        z.writestr(name, content.encode('utf-8'))
with ZipFile(target) as z:
    assert z.testzip() is None
    root = ET.fromstring(z.read('word/document.xml'))
    assert 'Power BI' in ''.join(root.itertext())
post_text = '\n\n'.join(POST)
(OUT / 'Publicacion_LinkedIn_Gastos_ETL.txt').write_text(post_text, encoding='utf-8')
print(f'DOCX creado y estructura XML validada: {target}')
print(f'Caracteres del texto de la publicación: {len(post_text)}')
