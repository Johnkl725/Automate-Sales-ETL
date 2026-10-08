from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    imap_host: str = "imap.gmail.com"
    imap_port: int = 993
    imap_user: str
    imap_app_password: str
    imap_mailbox: str = "INBOX"
    imap_processed_label: str = "Procesado-BCP"

    bcp_sender: str = "notificacionesbcp.com.pe"
    # Lista separada por comas de substrings de asunto a buscar en IMAP.
    # Cada EmailParser decide via can_parse() cual de estos correos sabe
    # procesar; esta lista solo acota la busqueda IMAP para no traer todo
    # el buzon del remitente.
    bcp_subject_hints: str = "Realizaste un consumo,CONSTANCIA DE PAGO DE SERVICIO"

    # Historico, congelado desde la migracion a SQL Server (ya no se escribe).
    duckdb_path: str = "./data/gastos.duckdb"
    checkpoint_path: str = "./data/checkpoint.json"

    timezone: str = "America/Lima"

    # --- SQL Server (modelo estrella, destino real del pipeline) ---
    mssql_host: str = "127.0.0.1"
    mssql_port: int = 1433
    mssql_database: str = "GastosBCP"
    mssql_user: str = "sa"
    mssql_sa_password: str = ""
    # La imagen de Airflow instala el Driver 18 (Dockerfile.airflow), pero
    # no todas las maquinas Windows lo tienen -- se puede apuntar al 17 via
    # .env si es lo unico instalado localmente (funciona igual de bien
    # contra SQL Server 2022, sin la sensibilidad al ping ICMP del 18).
    mssql_odbc_driver: str = "ODBC Driver 18 for SQL Server"

    @property
    def bcp_subject_hints_list(self) -> list[str]:
        return [hint.strip() for hint in self.bcp_subject_hints.split(",") if hint.strip()]

    @property
    def mssql_connection_string(self) -> str:
        # TrustServerCertificate=yes: el contenedor usa un certificado
        # autofirmado (no hay CA real detras de un SQL Server local de
        # desarrollo), sin esto pyodbc rechaza el handshake TLS.
        return (
            f"Driver={{{self.mssql_odbc_driver}}};"
            f"Server={self.mssql_host},{self.mssql_port};"
            f"Database={self.mssql_database};"
            f"UID={self.mssql_user};"
            f"PWD={self.mssql_sa_password};"
            "TrustServerCertificate=yes;"
        )


def get_settings() -> Settings:
    return Settings()
