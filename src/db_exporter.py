"""
Módulo Exportador a Base de Datos
Contiene la lógica para guardar los resultados en la base de datos.
"""
from typing import List
from sqlalchemy.orm import Session
from .data_models import Comprobante, Mensaje
import datetime
import uuid

class DbExporter:
    """
    Clase encargada de guardar los datos extraídos en la base de datos.
    """

    def get_or_create_mensaje(self, db: Session, message_id: str):
        """
        Busca un mensaje por su ID. Si no existe, lo crea.
        """
        mensaje = db.query(Mensaje).filter(Mensaje.message_id == message_id).first()
        if not mensaje:
            mensaje = Mensaje(message_id=message_id, timestamp=datetime.datetime.utcnow())
            db.add(mensaje)
            db.flush()
        return mensaje

    def exportar(self, db: Session, comprobante: Comprobante, message_id: str = None):
        """
        Guarda un único objeto Comprobante en la base de datos.
        """
        self.exportar_lista(db, [comprobante], message_id)

    def exportar_lista(self, db: Session, comprobantes: List[Comprobante], message_id: str = None):
        """
        Guarda una lista de objetos Comprobante en la base de datos.
        Evita duplicados verificando si el id_transferencia ya existe.
        """
        if not comprobantes:
            return
        
        # Set para rastrear IDs procesados en ESTE lote y evitar duplicados internos
        ids_en_lote = set()
        guardados = 0
        omitidos = 0

        try:
            if message_id:
                # Flujo original para mensajes (si se usa)
                mensaje = self.get_or_create_mensaje(db, message_id)
                for comp in comprobantes:
                    # TODO: Agregar lógica de deduplicación aquí también si fuera necesario
                    comp.mensaje_id = mensaje.id
                    db.add(comp)
            else:
                for comp in comprobantes:
                    # Si tiene ID de transferencia, verificamos duplicados
                    if comp.id_transferencia:
                        # 1. Chequeo en lote actual
                        if comp.id_transferencia in ids_en_lote:
                            print(f"  [Ignorado] Duplicado en lote: {comp.id_transferencia}")
                            omitidos += 1
                            continue
                        
                        # 2. Chequeo en Base de Datos (Más estricto: ID + Banco + Monto)
                        # Esto permite que dos bancos distintos tengan el mismo ID
                        existe = db.query(Comprobante).filter(
                            Comprobante.id_transferencia == comp.id_transferencia,
                            Comprobante.banco == comp.banco,
                            Comprobante.monto == comp.monto
                        ).first()
                        
                        if existe:
                            print(f"  [Ignorado] Ya existe en BD (ID+Banco+Monto coinciden): {comp.id_transferencia}")
                            omitidos += 1
                            continue
                        
                        ids_en_lote.add(comp.id_transferencia)

                    # Si llegamos aquí, es nuevo o no tiene ID (se permite insertar)
                    msg_id = comp.id_transferencia if comp.id_transferencia else str(uuid.uuid4())
                    mensaje = self.get_or_create_mensaje(db, msg_id)
                    comp.mensaje_id = mensaje.id
                    db.add(comp)
                    guardados += 1
            
            db.commit()
            print(f"Resumen de guardado: {guardados} nuevos, {omitidos} omitidos (duplicados).")
            
        except Exception as e:
            print(f"Error crítico al guardar en la base de datos: {e}")
            db.rollback()

