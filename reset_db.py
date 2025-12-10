from src.database import SessionLocal
from src.data_models import Mensaje, Comprobante
import sys

def reset_db():
    print("⚠️  ATENCIÓN: Esto borrará TODOS los datos de la base de datos.")
    confirm = input("¿Estás seguro? (escribe 'si' para confirmar): ")
    
    if confirm.lower() != 'si':
        print("Operación cancelada.")
        return

    db = SessionLocal()
    try:
        # Borramos primero los comprobantes (hijos) para no romper FK
        filas_c = db.query(Comprobante).delete()
        
        # Luego borramos los mensajes (padres)
        filas_m = db.query(Mensaje).delete()
        
        db.commit()
        print(f"✅ Base de datos limpia.")
        print(f"   - Comprobantes eliminados: {filas_c}")
        print(f"   - Mensajes eliminados: {filas_m}")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error al limpiar la base de datos: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    reset_db()
