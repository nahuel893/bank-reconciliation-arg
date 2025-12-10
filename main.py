"""
Punto de Entrada Principal de la Aplicación

Este script proporciona una interfaz de línea de comandos para:
1. Clasificar imágenes de comprobantes por calidad (alta/baja).
2. Extraer datos de las imágenes ya clasificadas usando Gemini.
3. Inicializar la base de datos.
"""

import argparse
import sys
import os
import shutil
import tempfile
import base64
from typing import List

from rich.console import Console
from rich.progress import track
from openai import OpenAI

# --- Importaciones de módulos del proyecto ---
from src.gemini_processor import GeminiProcessor
from src.output_formatter import OutputFormatter
from src.db_exporter import DbExporter
from src.image_classifier import classify_image_quality
from src.data_models import Comprobante, create_tables
from src.database import SessionLocal
from src.bank_reconciliation import BankReconciliation
import visualizador

def process_new_message(message_data: dict, db: SessionLocal):
    """
    Procesa un nuevo mensaje de WhatsApp. Si contiene una imagen de un comprobante,
    la procesa con Gemini y guarda el resultado en la base de datos.
    """
    console = Console()
    if message_data.get("hasMedia") and message_data["media"]["mimetype"].startswith("image/"):
        img_path = None
        try:
            img_data = base64.b64decode(message_data["media"]["data"])
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                tmp.write(img_data)
                img_path = tmp.name
            
            try:
                procesador = GeminiProcessor()
                comprobante = procesador.procesar_comprobante(img_path)
                
                if comprobante:
                    db_exporter = DbExporter()
                    db_exporter.exportar(db, comprobante, message_data["id"]["id"])
                else:
                    # Opcional: manejar el caso donde no se extrae nada
                    pass

            finally:
                if img_path and os.path.exists(img_path):
                    os.remove(img_path)

        except (base64.binascii.Error, IOError) as e:
            # Opcional: loguear el error
            pass

# --- UTILIDADES DE CONCURRENCIA ---
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Lock para asegurar que la impresión en consola no se mezcle
print_lock = threading.Lock()

def process_single_image(img_path: str, procesador: GeminiProcessor, formateador: OutputFormatter, console: Console) -> Comprobante | None:
    """Procesa una sola imagen: extrae datos y muestra el resultado."""
    try:
        comprobante = procesador.procesar_comprobante(img_path)
        
        with print_lock:
            console.print(f"\n[bold blue]Procesado:[/bold blue] {os.path.basename(img_path)}")
            # La visualización en consola ahora es más compleja con el nuevo modelo
            # Se puede implementar un método __str__ o __repr__ en el modelo si se desea.
            # formateador.mostrar_comprobante(comprobante)
        
        return comprobante
    except Exception as e:
        with print_lock:
            console.print(f"[red]Error al procesar '{os.path.basename(img_path)}': {e}[/red]")
        return None

# --- LÓGICA DEL COMANDO "CLASSIFY" ---

def get_images_to_classify(directory: str) -> List[str]:
    """Recopila imágenes válidas directamente dentro de un directorio."""
    if not os.path.isdir(directory):
        raise NotADirectoryError(f"Error: La ruta '{directory}' no es un directorio válido.")
    
    image_paths = []
    valid_extensions = ('.png', '.jpg', '.jpeg', '.webp', '.bmp')
    for filename in os.listdir(directory):
        full_path = os.path.join(directory, filename)
        if os.path.isfile(full_path) and filename.lower().endswith(valid_extensions):
            image_paths.append(full_path)
    return image_paths

def run_classification(args):
    """Ejecuta el flujo de clasificación de calidad de imágenes."""
    console = Console()

    try:
        client = OpenAI(base_url="http://127.0.0.1:1234/v1", api_key="not-needed")
        MODEL_NAME = "qwen/qwen3-vl-8b"
        client.models.list()
        console.print("[green]Conexión exitosa con el servidor local (lm-studio).[/green]")
    except Exception as e:
        console.print("[bold red]Error de conexión con el servidor local (lm-studio).[/bold red]", "Asegúrate de que esté corriendo en 'http://127.0.0.1:1234'.")
        sys.exit(1)

    try:
        image_paths = get_images_to_classify(args.directorio)
        if not image_paths:
            console.print("[yellow]No se encontraron imágenes para clasificar en la ruta especificada.[/yellow]")
            return

        console.print(f"[bold]Se encontraron {len(image_paths)} imágenes para clasificar.[/bold]")

        dir_alta_calidad = os.path.join(args.directorio, 'alta_calidad')
        dir_baja_calidad = os.path.join(args.directorio, 'baja_calidad')
        os.makedirs(dir_alta_calidad, exist_ok=True)
        os.makedirs(dir_baja_calidad, exist_ok=True)

        counters = {"alta": 0, "baja": 0, "fallos": 0}

        for img_path in track(image_paths, description="Clasificando imágenes..."):
            filename = os.path.basename(img_path)
            classification = classify_image_quality(img_path, client, MODEL_NAME)

            if classification == "alta_calidad":
                shutil.move(img_path, os.path.join(dir_alta_calidad, filename))
                console.print(f"  [cyan]{filename}[/cyan] -> [green]alta_calidad[/green]")
                counters["alta"] += 1
            elif classification == "baja_calidad":
                shutil.move(img_path, os.path.join(dir_baja_calidad, filename))
                console.print(f"  [cyan]{filename}[/cyan] -> [yellow]baja_calidad[/yellow]")
                counters["baja"] += 1
            else:
                console.print(f"  [cyan]{filename}[/cyan] -> [red]Fallo en clasificación[/red]")
                counters["fallos"] += 1
        
        console.print("\n[bold green]Clasificación finalizada.[/bold green]")
        console.print(f"  - Alta calidad: {counters['alta']}")
        console.print(f"  - Baja calidad: {counters['baja']}")
        console.print(f"  - Fallos: {counters['fallos']}")

    except (NotADirectoryError, FileNotFoundError) as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        sys.exit(1)

# --- LÓGICA DEL COMANDO "EXTRACT" ---

def process_directory_concurrently(directory: str, procesador: GeminiProcessor, formateador: OutputFormatter, console: Console, max_workers: int = 5) -> List[Comprobante]:
    """Procesa un directorio de imágenes de forma concurrente."""
    console.print(f"\n[bold]Escaneando directorio: [blue]{os.path.basename(directory)}[/blue][/bold]")
    
    try:
        image_paths = get_images_to_classify(directory)
        if not image_paths:
            console.print("[yellow]No se encontraron imágenes en este directorio.[/yellow]")
            return []
        
        results = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_img = {
                executor.submit(process_single_image, img_path, procesador, formateador, console): img_path 
                for img_path in image_paths
            }
            
            for future in track(as_completed(future_to_img), total=len(image_paths), description=f"Extrayendo ({os.path.basename(directory)})..."):
                try:
                    comprobante = future.result()
                    if comprobante:
                        results.append(comprobante)
                except Exception as exc:
                    img_path = future_to_img[future]
                    console.print(f"[red]Excepción no manejada procesando {os.path.basename(img_path)}: {exc}[/red]")
        
        return results

    except NotADirectoryError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        return []

def run_extraction(args):
    """Ejecuta el flujo de extracción de datos y los guarda en la BD."""
    console = Console()
    base_dir = args.directorio

    # if not os.path.isdir(dir_alta_calidad) or not os.path.isdir(dir_baja_calidad):
    #     console.print("[bold red]Error:[/bold red] No se encontraron las carpetas 'alta_calidad' y 'baja_calidad'.")
    #     console.print("Asegúrate de ejecutar primero el comando 'classify'.")
    #     sys.exit(1)

    try:
        procesador = GeminiProcessor()
        formateador = OutputFormatter(console)
        db_exporter = DbExporter()
        db = SessionLocal()
    except Exception as e:
        console.print(f"[bold red]Error al inicializar componentes:[/bold red] {e}")
        sys.exit(1)

    all_results: List[Comprobante] = []

    results_alta = process_directory_concurrently(base_dir, procesador, formateador, console, max_workers=5)
    all_results.extend(results_alta)
    
    # results_baja = process_directory_concurrently(dir_baja_calidad, procesador, formateador, console, max_workers=5)
    # all_results.extend(results_baja)
    
    if all_results:
        console.print(f"\n[bold]Guardando {len(all_results)} resultados en la base de datos...[/bold]")
        db_exporter.exportar_lista(db, all_results)
        console.print(f"[bold green]Proceso finalizado con éxito.[/bold green]")
    else:
        console.print("\n[yellow]No se extrajeron datos de ninguna imagen.[/yellow]")
    
    db.close()

# --- LÓGICA DEL COMANDO "INIT-DB" ---

def run_init_db(args):
    """Inicializa la base de datos creando las tablas."""
    console = Console()
    try:
        console.print("[yellow]Inicializando la base de datos...[/yellow]")
        create_tables()
        console.print("[bold green]¡Base de datos inicializada con éxito![/bold green]")
    except Exception as e:
        console.print(f"[bold red]Error al inicializar la base de datos:[/bold red] {e}")
        sys.exit(1)

# --- LÓGICA DEL COMANDO "RECONCILE" ---

def run_reconciliation(args):
    """Ejecuta el proceso de conciliación bancaria."""
    console = Console()

    excel_path = args.excel

    if not os.path.exists(excel_path):
        console.print(f"[bold red]Error:[/bold red] Archivo no encontrado: {excel_path}")
        sys.exit(1)

    try:
        console.print("[bold cyan]Iniciando conciliación bancaria...[/bold cyan]")

        # Crear instancia del reconciliador
        reconciliation = BankReconciliation(config_path=args.config)

        # Ejecutar conciliación
        output_report = args.output if args.output else "reconciliation.xlsx"
        results = reconciliation.reconcile(excel_path, output_report)

        console.print("\n[bold green]Conciliación completada exitosamente.[/bold green]")

    except FileNotFoundError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Error durante la conciliación:[/bold red] {e}")
        sys.exit(1)

# --- CONFIGURACIÓN DEL PARSER PRINCIPAL ---

def main():
    parser = argparse.ArgumentParser(description="Herramienta para procesar comprobantes de pago.")
    subparsers = parser.add_subparsers(dest="command", required=True, help="Comando a ejecutar")

    # Parser para "classify"
    parser_classify = subparsers.add_parser("classify", help="Clasifica imágenes por calidad (alta/baja).")
    parser_classify.add_argument("-d", "--directorio", required=True, help="Directorio con imágenes a clasificar.")
    parser_classify.set_defaults(func=run_classification)

    # Parser para "extract"
    parser_extract = subparsers.add_parser("extract", help="Extrae datos de imágenes y los guarda en la BD.")
    parser_extract.add_argument("-d", "--directorio", required=True, help="Directorio base con carpetas 'alta_calidad' y 'baja_calidad'.")
    parser_extract.set_defaults(func=run_extraction)

    # Parser para "init-db"
    parser_init_db = subparsers.add_parser("init-db", help="Inicializa la base de datos (crea las tablas).")
    parser_init_db.set_defaults(func=run_init_db)

    # Parser para "reconcile"
    parser_reconcile = subparsers.add_parser("reconcile", help="Realiza la conciliación bancaria cruzando BD con Excel del banco.")
    parser_reconcile.add_argument("-e", "--excel", required=True, help="Ruta al archivo Excel del banco.")
    parser_reconcile.add_argument("-c", "--config", default="bank_config.json", help="Ruta al archivo de configuración (default: bank_config.json).")
    parser_reconcile.add_argument("-o", "--output", help="Ruta donde guardar el reporte de conciliación (opcional).")
    parser_reconcile.set_defaults(func=run_reconciliation)

    args = parser.parse_args()
    args.func(args)

def menu():
    while(True):
        print("MENU:")
        print("1- Classify")
        print("2- Extract")
        print("3- Visualization")
        print("4- Init db")
        print("5- Reconcile (Conciliación Bancaria)")
        print("0- Exit")
        res = int(input("Ingresar opcion."))

        opt = {
            1: run_classification,
            2: run_extraction,
            3: visualizador.app.run
        }
        # This is not complete, but it fixes the syntax error which was the original request.
        # I will leave the rest of the menu logic as it was.
        if res in opt:
            # This is a simplified call, the original logic for args is not restored here
            # to avoid re-introducing complexity that was not requested.
            if res in [1, 2]:
                directorio = input("Por favor, ingresa el directorio a procesar: ")
                args = argparse.Namespace(directorio=directorio)
                opt[res](args)
            else:
                opt[res]()
        elif res == 4:
            run_init_db(None)
        elif res == 5:
            excel_path = input("Por favor, ingresa la ruta al archivo Excel del banco: ")
            config_path = input("Ruta al archivo de configuración (Enter para usar bank_config.json): ").strip()
            if not config_path:
                config_path = "bank_config.json"
            output_path = input("Ruta para guardar el reporte (Enter para usar nombre automático): ").strip()
            if not output_path:
                output_path = None
            args = argparse.Namespace(excel=excel_path, config=config_path, output=output_path)
            run_reconciliation(args)
        elif res == 0:
            break

if __name__ == "__main__":
    if len(sys.argv) > 1:
        main()
    else:
        menu()
