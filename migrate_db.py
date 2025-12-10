from sqlalchemy import text
from src.database import engine

def migrate_db():
    print("Iniciando migración de base de datos...")
    with engine.connect() as conn:
        conn.execution_options(isolation_level="AUTOCOMMIT")
        
        # 1. Agregar columna imagen_path
        try:
            conn.execute(text("ALTER TABLE comprobantes ADD COLUMN IF NOT EXISTS imagen_path VARCHAR;"))
            print("✔ Columna 'imagen_path' agregada/verificada.")
        except Exception as e:
            print(f"⚠ Error con imagen_path: {e}")

        # 2. Agregar campos de remitente
        new_cols = [
            "remitente_nombre", "remitente_id", "remitente_cuenta",
            "destinatario_nombre", "destinatario_id", "destinatario_cuenta"
        ]
        for col in new_cols:
            try:
                conn.execute(text(f"ALTER TABLE comprobantes ADD COLUMN IF NOT EXISTS {col} VARCHAR;"))
                print(f"✔ Columna '{col}' agregada/verificada.")
            except Exception as e:
                print(f"⚠ Error con {col}: {e}")

        # 3. Cambiar tipos de columnas (Monto y Fecha a String para compatibilidad inicial)
        # Nota: Esto puede fallar si ya hay datos que no se pueden convertir, pero como es dev asumimos que está bien.
        try:
            # PostgreSQL requiere una conversión explícita si cambiamos tipos drásticamente
            conn.execute(text("ALTER TABLE comprobantes ALTER COLUMN monto TYPE VARCHAR USING monto::varchar;"))
            conn.execute(text("ALTER TABLE comprobantes ALTER COLUMN fecha_transferencia TYPE VARCHAR USING fecha_transferencia::varchar;"))
            print("✔ Tipos de columnas 'monto' y 'fecha_transferencia' actualizados a VARCHAR.")
        except Exception as e:
            print(f"⚠ Error cambiando tipos de columnas: {e}")

    print("Migración finalizada.")

if __name__ == "__main__":
    migrate_db()
