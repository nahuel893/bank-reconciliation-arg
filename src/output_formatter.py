"""
Módulo del Formateador de Salida

Se encarga de presentar los datos extraídos de una manera clara
y legible en la consola.
"""
from rich.console import Console
from rich.table import Table
from .data_models import Comprobante

class OutputFormatter:
    """
    Formatea y muestra la información del comprobante en la consola.
    """
    def __init__(self, console: Console):
        self.console = console

    def mostrar_comprobante(self, comprobante: Comprobante):
        """
        Muestra los detalles de un comprobante en una tabla formateada.
        """
        if not comprobante:
            self.console.print("[yellow]No se pudo extraer información del comprobante.[/yellow]")
            return

        tabla = Table(title="[bold]Detalles del Comprobante[/bold]", show_header=True, header_style="bold magenta")
        tabla.add_column("Campo", style="dim", width=25)
        tabla.add_column("Valor")

        tabla.add_row("Banco Emisor", comprobante.banco or "No disponible")
        tabla.add_row("Monto", f"${comprobante.monto:,.2f}" if comprobante.monto is not None else "No disponible")
        tabla.add_row("Fecha de Transferencia", str(comprobante.fecha_transferencia) if comprobante.fecha_transferencia else "No disponible")
        tabla.add_row("ID de Transferencia", comprobante.id_transferencia or "No disponible")
        tabla.add_row("Detalle", comprobante.detalle or "No disponible")

        self.console.print(tabla)
