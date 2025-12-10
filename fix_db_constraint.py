from sqlalchemy import text
from src.database import engine

def remove_unique_constraint():
    print("Eliminando restricción UNIQUE de id_transferencia...")
    with engine.connect() as conn:
        conn.execution_options(isolation_level="AUTOCOMMIT")
        try:
            # El nombre de la restricción lo sacamos de tu mensaje de error anterior
            conn.execute(text("ALTER TABLE comprobantes DROP CONSTRAINT IF EXISTS comprobantes_id_transferencia_key;"))
            print("✔ Restricción eliminada con éxito.")
        except Exception as e:
            print(f"⚠ Error al eliminar restricción: {e}")

if __name__ == "__main__":
    remove_unique_constraint()
