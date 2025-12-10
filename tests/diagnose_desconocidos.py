"""
Script de Diagnóstico de Comprobantes DESCONOCIDO

Este script consulta la base de datos y muestra información detallada
sobre los comprobantes que quedaron con cliente_codigo = 'DESCONOCIDO'.

Uso: python tests/diagnose_desconocidos.py

Muestra:
- Lista de comprobantes DESCONOCIDO
- Información del mensaje asociado (author, timestamp, body)
- Ruta de la imagen
- Estadísticas generales
"""

import sys
import os
from datetime import datetime

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import SessionLocal
from src.data_models import Comprobante, Mensaje


def format_timestamp(ts):
    """Formatea un timestamp para mostrar."""
    if ts:
        return ts.strftime('%Y-%m-%d %H:%M:%S')
    return '(sin fecha)'


def diagnose_desconocidos():
    """Analiza los comprobantes con código DESCONOCIDO."""
    print("=" * 80)
    print("DIAGNÓSTICO DE COMPROBANTES DESCONOCIDO")
    print("=" * 80)

    db = SessionLocal()
    try:
        # Obtener todos los comprobantes DESCONOCIDO
        desconocidos = db.query(Comprobante).filter(
            Comprobante.cliente_codigo == 'DESCONOCIDO'
        ).order_by(Comprobante.id.desc()).all()

        total_comprobantes = db.query(Comprobante).count()
        total_desconocidos = len(desconocidos)

        print(f"\nTotal comprobantes en BD: {total_comprobantes}")
        print(f"Comprobantes DESCONOCIDO: {total_desconocidos}")
        print(f"Porcentaje: {(total_desconocidos/total_comprobantes*100):.1f}%" if total_comprobantes > 0 else "N/A")
        print("-" * 80)

        if not desconocidos:
            print("\n✅ No hay comprobantes con código DESCONOCIDO")
            return

        print(f"\nListado de {total_desconocidos} comprobantes DESCONOCIDO:\n")

        for i, comp in enumerate(desconocidos, 1):
            print(f"\n{'#' * 3} COMPROBANTE {i}/{total_desconocidos} {'#' * 50}")
            print(f"  ID Comprobante: {comp.id}")
            print(f"  Banco: {comp.banco or '(no detectado)'}")
            print(f"  Monto: {comp.monto or '(no detectado)'}")
            print(f"  Fecha transferencia: {comp.fecha_transferencia or '(no detectada)'}")
            print(f"  ID Transferencia: {comp.id_transferencia or '(no detectado)'}")
            print(f"  Imagen: {comp.imagen_path or '(sin imagen)'}")

            # Información del mensaje asociado
            if comp.mensaje:
                msg = comp.mensaje
                print(f"\n  --- Mensaje Asociado ---")
                print(f"  Message ID: {msg.message_id}")
                print(f"  Author: {msg.author or '(no registrado)'}")
                print(f"  Sender: {msg.sender or '(no registrado)'}")
                print(f"  Timestamp: {format_timestamp(msg.timestamp)}")
                print(f"  Body: \"{msg.body or '(vacío)'}\"")
            else:
                print(f"\n  ⚠️  Sin mensaje asociado en BD")

            # Verificar si la imagen existe
            if comp.imagen_path:
                if os.path.exists(comp.imagen_path):
                    size_kb = os.path.getsize(comp.imagen_path) / 1024
                    print(f"\n  ✅ Imagen existe ({size_kb:.1f} KB)")
                else:
                    print(f"\n  ❌ Imagen NO existe en disco")

        # Estadísticas por author
        print("\n" + "=" * 80)
        print("ESTADÍSTICAS POR AUTHOR:")
        print("-" * 80)

        authors = {}
        for comp in desconocidos:
            if comp.mensaje and comp.mensaje.author:
                author = comp.mensaje.author
                authors[author] = authors.get(author, 0) + 1

        if authors:
            for author, count in sorted(authors.items(), key=lambda x: -x[1]):
                print(f"  {author}: {count} DESCONOCIDO(s)")
        else:
            print("  (No hay información de authors)")

        print("\n" + "=" * 80)

    except Exception as e:
        print(f"\n❌ Error durante el diagnóstico: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


def export_desconocidos_csv():
    """Exporta los DESCONOCIDO a un archivo CSV."""
    import csv

    db = SessionLocal()
    try:
        desconocidos = db.query(Comprobante).filter(
            Comprobante.cliente_codigo == 'DESCONOCIDO'
        ).all()

        csv_path = os.path.join(os.path.dirname(__file__), 'desconocidos_export.csv')

        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'comprobante_id', 'banco', 'monto', 'fecha_transferencia',
                'id_transferencia', 'imagen_path', 'message_id', 'author',
                'sender', 'body', 'timestamp'
            ])

            for comp in desconocidos:
                msg = comp.mensaje
                writer.writerow([
                    comp.id,
                    comp.banco,
                    comp.monto,
                    comp.fecha_transferencia,
                    comp.id_transferencia,
                    comp.imagen_path,
                    msg.message_id if msg else '',
                    msg.author if msg else '',
                    msg.sender if msg else '',
                    msg.body if msg else '',
                    format_timestamp(msg.timestamp) if msg else ''
                ])

        print(f"\n📄 Exportado a: {csv_path}")

    finally:
        db.close()


if __name__ == "__main__":
    diagnose_desconocidos()

    # Preguntar si exportar a CSV
    print("\n¿Exportar a CSV? (s/n): ", end="")
    try:
        resp = input().strip().lower()
        if resp == 's':
            export_desconocidos_csv()
    except (EOFError, KeyboardInterrupt):
        pass
