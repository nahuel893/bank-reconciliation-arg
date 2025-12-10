"""
Módulo de Modelos de Datos

Define las clases de datos para estructurar la información extraída
de los comprobantes de pago usando SQLAlchemy.
"""
from sqlalchemy import Column, Integer, String, create_engine, DateTime, ForeignKey, Float, Boolean
from sqlalchemy.orm import relationship
from .database import Base, engine
import datetime

class Mensaje(Base):
    """
    Define el modelo de la tabla 'mensajes' para almacenar los detalles de los mensajes
    que contienen comprobantes de pago.
    """
    __tablename__ = 'mensajes'

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(String, unique=True, nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    sender = Column(String, nullable=True)  # Remitente del mensaje de WhatsApp (grupo)
    author = Column(String, nullable=True)  # Autor real del mensaje (número o contacto)
    body = Column(String, nullable=True)    # Contenido del mensaje de texto

    # Relación con Comprobante
    comprobantes = relationship("Comprobante", back_populates="mensaje")

    def __repr__(self):
        return f"<Mensaje(id={self.id}, message_id='{self.message_id}')>"

class Comprobante(Base):
    """
    Define el modelo de la tabla 'comprobantes' para almacenar la información
    extraída de un comprobante de transferencia.
    """
    __tablename__ = 'comprobantes'

    id = Column(Integer, primary_key=True, index=True)
    banco = Column(String, nullable=True)
    monto = Column(String, nullable=True)  # Cambiado a String para flexibilidad inicial
    fecha_transferencia = Column(String, nullable=True) # Cambiado a String para flexibilidad inicial
    id_transferencia = Column(String, nullable=True) # Se permite duplicados (diferentes bancos)
    detalle = Column(String, nullable=True)
    imagen_path = Column(String, nullable=True)

    # Campos nuevos para remitente y destinatario
    remitente_nombre = Column(String, nullable=True)
    remitente_id = Column(String, nullable=True)
    remitente_cuenta = Column(String, nullable=True)

    destinatario_nombre = Column(String, nullable=True)
    destinatario_id = Column(String, nullable=True)
    destinatario_cuenta = Column(String, nullable=True)

    cliente_codigo = Column(String, nullable=True)  # Código de cliente extraído del mensaje

    # Campos de conciliación bancaria
    conciliado = Column(Boolean, default=False, nullable=True)
    fecha_conciliacion = Column(DateTime, nullable=True)
    observaciones_conciliacion = Column(String, nullable=True)

    mensaje_id = Column(Integer, ForeignKey('mensajes.id'))

    # Relación con Mensaje
    mensaje = relationship("Mensaje", back_populates="comprobantes")

    def __repr__(self):
        return f"<Comprobante(id={self.id}, banco='{self.banco}', monto='{self.monto}')>"

def create_tables():
    """Crea todas las tablas en la base de datos."""
    Base.metadata.create_all(bind=engine)