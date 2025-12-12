"""
Módulo de Logging Centralizado

Proporciona una clase Logger configurable para todo el proyecto.
Soporta múltiples niveles de log, salida a consola y archivo,
y formato personalizable.
"""
import logging
import os
from datetime import datetime
from typing import Optional
from logging.handlers import RotatingFileHandler

from config import PROJECT_ROOT


class AppLogger:
    """
    Clase singleton para logging centralizado.

    Uso:
        from src.logger import AppLogger

        logger = AppLogger.get_logger("mi_modulo")
        logger.info("Mensaje informativo")
        logger.error("Mensaje de error")
    """

    _loggers: dict = {}
    _initialized: bool = False
    _log_dir: str = os.path.join(PROJECT_ROOT, "logs")
    _log_level: int = logging.DEBUG
    _log_to_file: bool = True
    _log_to_console: bool = True
    _max_file_size: int = 5 * 1024 * 1024  # 5 MB
    _backup_count: int = 3

    # Formato de los mensajes
    _console_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    _file_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(filename)s:%(lineno)d | %(message)s"
    _date_format = "%Y-%m-%d %H:%M:%S"

    @classmethod
    def configure(
        cls,
        log_level: int = logging.INFO,
        log_to_file: bool = True,
        log_to_console: bool = True,
        log_dir: Optional[str] = None,
        max_file_size: int = 5 * 1024 * 1024,
        backup_count: int = 3
    ) -> None:
        """
        Configura el sistema de logging.

        Args:
            log_level: Nivel mínimo de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            log_to_file: Si True, escribe logs a archivo
            log_to_console: Si True, muestra logs en consola
            log_dir: Directorio para archivos de log
            max_file_size: Tamaño máximo de archivo antes de rotar (bytes)
            backup_count: Número de archivos de backup a mantener
        """
        cls._log_level = log_level
        cls._log_to_file = log_to_file
        cls._log_to_console = log_to_console
        cls._max_file_size = max_file_size
        cls._backup_count = backup_count

        if log_dir:
            cls._log_dir = log_dir

        # Crear directorio de logs si no existe
        if cls._log_to_file and not os.path.exists(cls._log_dir):
            os.makedirs(cls._log_dir)

        cls._initialized = True

        # Reconfigurar loggers existentes
        for logger in cls._loggers.values():
            cls._setup_handlers(logger)

    @classmethod
    def _setup_handlers(cls, logger: logging.Logger) -> None:
        """Configura los handlers para un logger."""
        # Limpiar handlers existentes
        logger.handlers.clear()
        logger.setLevel(cls._log_level)

        # Handler de consola
        if cls._log_to_console:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(cls._log_level)
            console_formatter = logging.Formatter(
                cls._console_format,
                datefmt=cls._date_format
            )
            console_handler.setFormatter(console_formatter)
            logger.addHandler(console_handler)

        # Handler de archivo con rotación
        if cls._log_to_file:
            log_file = os.path.join(
                cls._log_dir,
                f"app_{datetime.now().strftime('%Y-%m-%d')}.log"
            )
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=cls._max_file_size,
                backupCount=cls._backup_count,
                encoding='utf-8'
            )
            file_handler.setLevel(cls._log_level)
            file_formatter = logging.Formatter(
                cls._file_format,
                datefmt=cls._date_format
            )
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)

    @classmethod
    def get_logger(cls, name: str) -> logging.Logger:
        """
        Obtiene o crea un logger con el nombre especificado.

        Args:
            name: Nombre del logger (típicamente el nombre del módulo)

        Returns:
            logging.Logger: Logger configurado

        Ejemplo:
            logger = AppLogger.get_logger("gemini_processor")
            logger.info("Procesando imagen...")
        """
        if name in cls._loggers:
            return cls._loggers[name]

        # Crear nuevo logger
        logger = logging.getLogger(f"comprobantes.{name}")
        logger.propagate = False  # Evitar duplicación de logs

        # Inicializar con configuración por defecto si no se ha configurado
        if not cls._initialized:
            if cls._log_to_file and not os.path.exists(cls._log_dir):
                os.makedirs(cls._log_dir)
            cls._initialized = True

        cls._setup_handlers(logger)
        cls._loggers[name] = logger

        return logger

    @classmethod
    def set_level(cls, level: int) -> None:
        """
        Cambia el nivel de logging para todos los loggers.

        Args:
            level: Nuevo nivel (logging.DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        cls._log_level = level
        for logger in cls._loggers.values():
            logger.setLevel(level)
            for handler in logger.handlers:
                handler.setLevel(level)

    @classmethod
    def disable_file_logging(cls) -> None:
        """Desactiva el logging a archivo."""
        cls._log_to_file = False
        for logger in cls._loggers.values():
            logger.handlers = [
                h for h in logger.handlers
                if not isinstance(h, RotatingFileHandler)
            ]

    @classmethod
    def disable_console_logging(cls) -> None:
        """Desactiva el logging a consola."""
        cls._log_to_console = False
        for logger in cls._loggers.values():
            logger.handlers = [
                h for h in logger.handlers
                if not isinstance(h, logging.StreamHandler)
                or isinstance(h, RotatingFileHandler)
            ]


# Funciones de conveniencia para uso rápido
def get_logger(name: str) -> logging.Logger:
    """Atajo para AppLogger.get_logger()"""
    return AppLogger.get_logger(name)


def configure_logging(**kwargs) -> None:
    """Atajo para AppLogger.configure()"""
    AppLogger.configure(**kwargs)
