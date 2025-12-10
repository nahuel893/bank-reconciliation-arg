"""
Módulo de Configuración

Carga y proporciona acceso a las configuraciones de la aplicación,
como las claves de API, desde un archivo .env.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    """
    Configuración de la aplicación cargada desde variables de entorno.
    """
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore'
    )

    GEMINI_API_KEY: str = Field(..., description="Clave de API para Google Gemini")
    POSTGRES_USER: str = Field(..., description="Usuario de PostgreSQL")
    POSTGRES_PASSWORD: str = Field(..., description="Contraseña de PostgreSQL")
    DATABASE: str = Field(..., description="Nombre de la base de datos PostgreSQL")
    IP_SERVER: str = Field(..., description="Direccion ip del servidor")

# Crear una instancia de Settings para ser usada en toda la aplicación
settings = Settings()
