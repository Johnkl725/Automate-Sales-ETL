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

    duckdb_path: str = "./data/gastos.duckdb"
    checkpoint_path: str = "./data/checkpoint.json"

    timezone: str = "America/Lima"

    @property
    def bcp_subject_hints_list(self) -> list[str]:
        return [hint.strip() for hint in self.bcp_subject_hints.split(",") if hint.strip()]


def get_settings() -> Settings:
    return Settings()
