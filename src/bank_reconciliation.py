"""
Módulo de Conciliación Bancaria

Este módulo realiza el cruce entre los comprobantes almacenados en la base de datos
y los movimientos registrados en el Excel del banco, usando las claves:
- Fecha de transferencia
- CUIT/CUIL del remitente o destinatario
- Monto de la transacción

Genera reportes detallados y actualiza el estado de conciliación en la base de datos.
"""
import json
import os
import re
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import pandas as pd
from sqlalchemy import text
 
# Local imports 
from .database import SessionLocal
from .data_models import Comprobante
from rich.console import Console
from rich.table import Table
from rich.progress import track

console = Console()


class BankReconciliation:
    """Clase principal para realizar la conciliación bancaria."""

    def __init__(self, config_path: str = "bank_config.json"):
        """
        Inicializa el módulo de conciliación.

        Args:
            config_path: Ruta al archivo de configuración JSON
        """
        self.config = self._load_config(config_path)
        self.db = SessionLocal()

    def _load_config(self, config_path: str) -> Dict:
        """Carga la configuración desde el archivo JSON."""
        if not os.path.exists(config_path):
            raise FileNotFoundError(
                f"Archivo de configuración no encontrado: {config_path}\n"
                "Copia bank_config.json.example a bank_config.json y ajusta los valores."
            )

        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _normalize_cuit(self, cuit: str) -> str:
        """
        Normaliza un CUIT/CUIL removiendo guiones y espacios.

        Args:
            cuit: CUIT en cualquier formato

        Returns:
            CUIT sin guiones ni espacios
        """
        if pd.isna(cuit) or not cuit:
            return ""

        # Convertir a string y remover guiones, espacios y puntos
        return str(cuit).replace("-", "").replace(" ", "").replace(".", "").strip()

    def _normalize_monto(self, monto: str) -> float:
        """
        Normaliza un monto, manejando diferentes formatos numéricos.

        Args:
            monto: Monto como string (ej: "1.000,50" o "1000.50")

        Returns:
            Monto como float
        """
        if pd.isna(monto) or not monto:
            return 0.0

        # Convertir a string
        monto_str = str(monto).strip()

        # Remover símbolos de moneda
        monto_str = re.sub(r'[$\s]', '', monto_str)

        # Detectar formato (argentino usa . para miles y , para decimales)
        decimal_sep = self.config['data_formats'].get('monto_decimal_separator', ',')
        thousands_sep = self.config['data_formats'].get('monto_thousands_separator', '.')

        if decimal_sep == ',':
            # Formato argentino: 1.000,50 → 1000.50
            monto_str = monto_str.replace(thousands_sep, '').replace(decimal_sep, '.')

        try:
            return float(monto_str)
        except ValueError:
            console.print(f"[yellow]Advertencia: No se pudo convertir monto '{monto}' a número[/yellow]")
            return 0.0

    def _parse_fecha(self, fecha: str) -> Optional[datetime]:
        """
        Parsea una fecha desde string a datetime.

        Args:
            fecha: Fecha como string

        Returns:
            Objeto datetime o None si no se pudo parsear
        """
        if pd.isna(fecha) or not fecha:
            return None

        # Si ya es datetime, retornar directamente
        if isinstance(fecha, datetime):
            return fecha

        fecha_format = self.config['data_formats'].get('fecha_format', '%d/%m/%Y')

        try:
            return datetime.strptime(str(fecha).strip(), fecha_format)
        except ValueError:
            # Intentar con formatos comunes
            common_formats = ['%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%Y/%m/%d']
            for fmt in common_formats:
                try:
                    return datetime.strptime(str(fecha).strip(), fmt)
                except ValueError:
                    continue

            console.print(f"[yellow]Advertencia: No se pudo parsear fecha '{fecha}'[/yellow]")
            return None

    def load_bank_excel(self, excel_path: str) -> pd.DataFrame:
        """
        Carga y normaliza el Excel del banco.

        Args:
            excel_path: Ruta al archivo Excel

        Returns:
            DataFrame con los datos del banco normalizados
        """
        console.print(f"\n[cyan]Cargando Excel del banco: {excel_path}[/cyan]")

        # Opciones de lectura del Excel
        sheet_name = self.config['excel_options'].get('sheet_name', 0)
        header_row = self.config['excel_options'].get('header_row', 0)
        skip_rows = self.config['excel_options'].get('skip_rows', 0)

        # Leer Excel
        df = pd.read_excel(
            excel_path,
            sheet_name=sheet_name,
            header=header_row,
            skiprows=range(skip_rows) if skip_rows > 0 else None
        )

        # Mapeo de columnas
        col_mapping = self.config['column_mapping']

        # Verificar que las columnas existen
        missing_cols = [col for col in col_mapping.values() if col not in df.columns]
        if missing_cols:
            console.print(f"[red]Error: Columnas faltantes en el Excel: {missing_cols}[/red]")
            console.print(f"[yellow]Columnas disponibles: {list(df.columns)}[/yellow]")
            raise ValueError(f"Columnas faltantes: {missing_cols}")

        # Renombrar columnas para estandarizar
        df = df.rename(columns={
            col_mapping['fecha']: 'fecha',
            col_mapping['cuit']: 'cuit',
            col_mapping['monto']: 'monto'
        })

        # Normalizar datos
        df['cuit_norm'] = df['cuit'].apply(self._normalize_cuit)
        df['monto_norm'] = df['monto'].apply(self._normalize_monto)
        df['fecha_norm'] = df['fecha'].apply(self._parse_fecha)

        # Filtrar filas sin datos válidos
        df = df.dropna(subset=['fecha_norm', 'cuit_norm'])
        df = df[df['monto_norm'] > 0]

        console.print(f"[green]✓ Cargados {len(df)} registros del banco[/green]")

        return df

    def load_comprobantes_from_db(self) -> pd.DataFrame:
        """
        Carga los comprobantes desde la base de datos.

        Returns:
            DataFrame con los comprobantes de la BD
        """
        console.print("\n[cyan]Cargando comprobantes de la base de datos...[/cyan]")

        query = """
            SELECT
                c.id,
                c.banco,
                c.monto,
                c.fecha_transferencia,
                c.remitente_id,
                c.destinatario_id,
                c.cliente_codigo,
                c.imagen_path,
                c.conciliado
            FROM comprobantes c
        """

        df = pd.read_sql(query, self.db.bind)

        # Normalizar datos
        df['monto_norm'] = df['monto'].apply(self._normalize_monto)
        df['fecha_norm'] = df['fecha_transferencia'].apply(self._parse_fecha)
        df['remitente_id_norm'] = df['remitente_id'].apply(self._normalize_cuit)
        df['destinatario_id_norm'] = df['destinatario_id'].apply(self._normalize_cuit)

        console.print(f"[green]✓ Cargados {len(df)} comprobantes de la BD[/green]")

        return df

    def match_records(self, df_banco: pd.DataFrame, df_comprobantes: pd.DataFrame) -> Dict:
        """
        Realiza el matching entre registros del banco y comprobantes.

        Args:
            df_banco: DataFrame del banco
            df_comprobantes: DataFrame de comprobantes

        Returns:
            Diccionario con los resultados del matching
        """
        console.print("\n[cyan]Realizando matching de registros...[/cyan]")

        tolerancia_dias = self.config['tolerances'].get('fecha_dias', 1)
        tolerancia_monto = self.config['tolerances'].get('monto_diferencia', 0.01)

        matches = []
        matched_banco_idx = set()
        matched_comprobantes_idx = set()

        # Iterar sobre registros del banco
        for idx_banco, row_banco in track(df_banco.iterrows(), total=len(df_banco),
                                          description="Buscando coincidencias"):
            fecha_banco = row_banco['fecha_norm']
            cuit_banco = row_banco['cuit_norm']
            monto_banco = row_banco['monto_norm']

            # Buscar coincidencias en comprobantes
            for idx_comp, row_comp in df_comprobantes.iterrows():
                # Saltar si ya fue matched
                if idx_comp in matched_comprobantes_idx:
                    continue

                fecha_comp = row_comp['fecha_norm']
                monto_comp = row_comp['monto_norm']

                # Verificar CUIT (puede ser remitente o destinatario)
                cuit_match = (
                    cuit_banco == row_comp['remitente_id_norm']
                )

                if not cuit_match:
                    continue

                # Verificar fecha con tolerancia
                if fecha_comp and fecha_banco:
                    fecha_diff = abs((fecha_comp - fecha_banco).days)
                    fecha_match = fecha_diff <= tolerancia_dias
                else:
                    fecha_match = False

                # Verificar monto con tolerancia
                monto_diff = abs(monto_comp - monto_banco)
                monto_match = monto_diff <= tolerancia_monto

                # Si todo coincide, es un match
                if fecha_match and monto_match:
                    matches.append({
                        'comprobante_id': row_comp['id'],
                        'banco_idx': idx_banco,
                        'fecha_diff_dias': fecha_diff,
                        'monto_diff': monto_diff,
                        'banco_row': row_banco,
                        'comprobante_row': row_comp
                    })
                    matched_banco_idx.add(idx_banco)
                    matched_comprobantes_idx.add(idx_comp)
                    break  # Un comprobante solo puede matchear una vez

        # Registros sin match
        unmatched_banco = df_banco[~df_banco.index.isin(matched_banco_idx)]
        unmatched_comprobantes = df_comprobantes[~df_comprobantes.index.isin(matched_comprobantes_idx)]

        console.print(f"[green]✓ Matching completado[/green]")
        console.print(f"  - Coincidencias encontradas: {len(matches)}")
        console.print(f"  - Registros del banco sin match: {len(unmatched_banco)}")
        console.print(f"  - Comprobantes sin match: {len(unmatched_comprobantes)}")

        return {
            'matches': matches,
            'unmatched_banco': unmatched_banco,
            'unmatched_comprobantes': unmatched_comprobantes
        }

    def update_database(self, matches: List[Dict]) -> int:
        """
        Actualiza la base de datos marcando los comprobantes conciliados.

        Args:
            matches: Lista de matches encontrados

        Returns:
            Número de registros actualizados
        """
        console.print("\n[cyan]Actualizando base de datos...[/cyan]")

        comprobante_ids = [m['comprobante_id'] for m in matches]

        if not comprobante_ids:
            console.print("[yellow]No hay registros para actualizar[/yellow]")
            return 0

        try:
            # Actualizar en batch
            update_query = text("""
                UPDATE comprobantes
                SET conciliado = TRUE,
                    fecha_conciliacion = :fecha_conciliacion,
                    observaciones_conciliacion = 'Conciliado automáticamente'
                WHERE id = ANY(:ids)
            """)

            result = self.db.execute(update_query, {
                'fecha_conciliacion': datetime.now(),
                'ids': comprobante_ids
            })

            self.db.commit()

            console.print(f"[green]✓ {len(comprobante_ids)} comprobantes marcados como conciliados[/green]")
            return len(comprobante_ids)

        except Exception as e:
            self.db.rollback()
            console.print(f"[red]Error al actualizar base de datos: {e}[/red]")
            raise

    def generate_report(self, results: Dict, output_path: str):
        """
        Genera un reporte en Excel con los resultados de la conciliación.

        Args:
            results: Resultados del matching
            output_path: Ruta donde guardar el reporte
        """
        console.print(f"\n[cyan]Generando reporte en: {output_path}[/cyan]")

        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            # Hoja 1: Conciliados
            if results['matches']:
                df_matched = pd.DataFrame([
                    {
                        'ID Comprobante': m['comprobante_id'],
                        'Cliente Código': m['comprobante_row']['cliente_codigo'],
                        'Banco': m['comprobante_row']['banco'],
                        'Fecha Comprobante': m['comprobante_row']['fecha_transferencia'],
                        'Fecha Banco': m['banco_row']['fecha'],
                        'Diferencia Días': m['fecha_diff_dias'],
                        'Monto Comprobante': m['comprobante_row']['monto'],
                        'Monto Banco': m['banco_row']['monto'],
                        'Diferencia Monto': m['monto_diff'],
                        'Imagen': m['comprobante_row']['imagen_path']
                    }
                    for m in results['matches']
                ])
                df_matched.to_excel(writer, sheet_name='Conciliados', index=False)

            # Hoja 2: Faltantes en BD (están en banco pero no en BD)
            if not results['unmatched_banco'].empty:
                df_unmatched_banco = results['unmatched_banco'][['fecha', 'cuit', 'monto']].copy()
                df_unmatched_banco.to_excel(writer, sheet_name='Faltantes en BD', index=False)

            # Hoja 3: Faltantes en Banco (están en BD pero no en banco)
            if not results['unmatched_comprobantes'].empty:
                df_unmatched_comp = results['unmatched_comprobantes'][
                    ['id', 'cliente_codigo', 'banco', 'fecha_transferencia', 'monto', 'imagen_path']
                ].copy()
                df_unmatched_comp.to_excel(writer, sheet_name='Faltantes en Banco', index=False)

        console.print(f"[green]✓ Reporte generado exitosamente[/green]")

    def print_summary(self, results: Dict):
        """
        Imprime un resumen en consola de los resultados.

        Args:
            results: Resultados del matching
        """
        table = Table(title="\nResumen de Conciliación Bancaria")

        table.add_column("Categoría", style="cyan")
        table.add_column("Cantidad", style="magenta", justify="right")

        table.add_row("Conciliados", str(len(results['matches'])))
        table.add_row("Faltantes en BD", str(len(results['unmatched_banco'])))
        table.add_row("Faltantes en Banco", str(len(results['unmatched_comprobantes'])))

        console.print(table)

    def reconcile(self, excel_path: str, output_report_path: str = ".") -> Dict:
        """
        Ejecuta el proceso completo de conciliación.

        Args:
            excel_path: Ruta al Excel del banco
            output_report_path: Ruta donde guardar el reporte (opcional)

        Returns:
            Diccionario con los resultados
        """
        try:
            # 1. Cargar datos
            df_banco = self.load_bank_excel(excel_path)
            df_comprobantes = self.load_comprobantes_from_db()

            # 2. Realizar matching
            results = self.match_records(df_banco, df_comprobantes)

            # 3. Actualizar base de datos
            self.update_database(results['matches'])

            # 4. Generar reporte
            if output_report_path is None:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                output_report_path = f"reporte_conciliacion_{timestamp}.xlsx"

            self.generate_report(results, output_report_path)

            # 5. Mostrar resumen
            self.print_summary(results)

            return results

        except Exception as e:
            console.print(f"[red]Error durante la conciliación: {e}[/red]")
            raise
        finally:
            self.db.close()

def main():
    """Función principal para ejecutar desde CLI."""
    import sys

    if len(sys.argv) < 2:
        console.print("[red]Error: Debes proporcionar la ruta al Excel del banco[/red]")
        console.print("Uso: python -m src.bank_reconciliation <ruta_excel>")
        console.print("[yellow]Usando ruta por default[yellow]")
        #sys.exit(1)
        excel_path = '../assets/banco/Ultimos_Movimientos.xls'
    else:
        excel_path = sys.argv[1]

    if not os.path.exists(excel_path):
        console.print(f"[red]Error: Archivo no encontrado: {excel_path}[/red]")
        sys.exit(1)
    console.print("Testeando datos del banco post transformacion")  
    reconciliation = BankReconciliation()
    reconciliation.reconcile(excel_path)


if __name__ == "__main__":
    main()
