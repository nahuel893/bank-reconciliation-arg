"""
Módulo de Configuración

Carga y proporciona acceso a las configuraciones de la aplicación,
como las claves de API, desde un archivo .env.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
import json
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class Settings(BaseSettings):
    """
    Configuración de la aplicación cargada desde variables de entorno.
    """
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore'
    )
    # Net config
    GEMINI_API_KEY: str = Field(..., description="Clave de API para Google Gemini")
    POSTGRES_USER: str = Field(..., description="Usuario de PostgreSQL")
    POSTGRES_PASSWORD: str = Field(..., description="Contraseña de PostgreSQL")
    DATABASE: str = Field(..., description="Nombre de la base de datos PostgreSQL")
    IP_SERVER: str = Field(..., description="Direccion ip del servidor")
    BANK_ASSETS_DIR: str = Field(default="assets/bank/", description="Ruta de los archivos del banco")
    BANK_CONFIG_FILE: str = Field(default="assets/bank/bank_config.json", description="Configuracion excel banco")
      
# Crear una instancia de Settings para ser usada en toda la aplicación
settings = Settings()

# Bank config
bank_config = None
def get_bank_config():
    global bank_config
    with open(os.path.join(PROJECT_ROOT,settings.BANK_CONFIG_FILE), "r") as file:
        bank_config = json.load(file)
    return bank_config




      
         
    

     
