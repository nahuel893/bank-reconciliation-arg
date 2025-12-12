import tkinter as tk
from tkinter import ttk, scrolledtext
import subprocess
import threading
import sys
import os
import queue
import signal

# Configuración de Colores (Tema Oscuro)
BG_COLOR = "#1e1e1e"
FG_COLOR = "#d4d4d4"
TEXT_BG = "#252526"
HEADER_BG = "#333333"
ACCENT_COLOR = "#007acc"
ERROR_COLOR = "#f44747"
SUCCESS_COLOR = "#4ec9b0"

class ProcessTab(ttk.Frame):
    """
    Panel individual para manejar un subproceso y mostrar sus logs.
    """
    def __init__(self, parent, title, command, cwd=None):
        super().__init__(parent)
        self.command = command
        self.cwd = cwd
        self.process = None
        self.queue = queue.Queue()
        self.stop_event = threading.Event()
        self.is_running = False

        # Configurar UI del Panel
        self.create_widgets(title)
        
        # Iniciar polling de la cola de mensajes
        self.after(100, self.update_logs)

    def create_widgets(self, title):
        # Barra de control superior
        control_frame = tk.Frame(self, bg=HEADER_BG, height=40)
        control_frame.pack(fill=tk.X, side=tk.TOP)
        
        # Título
        lbl_title = tk.Label(control_frame, text=title, font=("Consolas", 12, "bold"), 
                             bg=HEADER_BG, fg="white", padx=10, pady=5)
        lbl_title.pack(side=tk.LEFT)

        # Botón Detener
        self.btn_stop = tk.Button(control_frame, text="⏹ Detener", command=self.stop_process,
                                  bg="#c42b1c", fg="white", state=tk.DISABLED, relief=tk.FLAT)
        self.btn_stop.pack(side=tk.RIGHT, padx=5, pady=5)

        # Botón Iniciar
        self.btn_start = tk.Button(control_frame, text="▶ Iniciar", command=self.start_process,
                                   bg="#3b8640", fg="white", relief=tk.FLAT)
        self.btn_start.pack(side=tk.RIGHT, padx=5, pady=5)

        # Área de Logs
        self.log_area = scrolledtext.ScrolledText(self, state=tk.DISABLED, bg=TEXT_BG, fg=FG_COLOR,
                                                  font=("Consolas", 10), selectbackground="#264f78")
        self.log_area.pack(expand=True, fill=tk.BOTH, padx=0, pady=0)
        
        # Tags para colores
        self.log_area.tag_config("stderr", foreground=ERROR_COLOR)
        self.log_area.tag_config("info", foreground=SUCCESS_COLOR)
        self.log_area.tag_config("system", foreground=ACCENT_COLOR)

    def append_log(self, text, tag=None):
        self.log_area.configure(state=tk.NORMAL)
        self.log_area.insert(tk.END, text, tag)
        self.log_area.see(tk.END)
        self.log_area.configure(state=tk.DISABLED)

    def read_stream(self, pipe, tag):
        """Lee salida del subproceso y la pone en la cola."""
        try:
            for line in iter(pipe.readline, ''):
                self.queue.put((line, tag))
                if self.stop_event.is_set():
                    break
        except Exception:
            pass
        finally:
            pipe.close()

    def update_logs(self):
        """Consume la cola y actualiza la GUI."""
        while not self.queue.empty():
            try:
                msg, tag = self.queue.get_nowait()
                self.append_log(msg, tag)
            except queue.Empty:
                break
        
        # Verificar si el proceso murió inesperadamente
        if self.is_running and self.process and self.process.poll() is not None:
            self.is_running = False
            self.append_log(f"\n[SISTEMA] El proceso terminó con código {self.process.returncode}\n", "system")
            self.toggle_buttons(running=False)

        self.after(100, self.update_logs)

    def start_process(self):
        if self.is_running:
            return

        self.stop_event.clear()
        try:
            # shell=False es más seguro, pero necesitamos dividir comandos
            # En Windows shell=True es a veces necesario para encontrar comandos del sistema, 
            # pero en Linux preferimos lista directa.
            cmd_list = self.command.split() if isinstance(self.command, str) else self.command
            
            # Usar 'setsid' en Linux permite matar todo el grupo de procesos hijos (útil para npm start)
            preexec_fn = os.setsid if sys.platform != "win32" else None

            self.process = subprocess.Popen(
                cmd_list,
                cwd=self.cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # Line buffered
                preexec_fn=preexec_fn
            )
            
            self.is_running = True
            self.toggle_buttons(running=True)
            self.append_log(f"[SISTEMA] Iniciando: {self.command}\n", "system")

            # Hilos para leer stdout y stderr
            t_out = threading.Thread(target=self.read_stream, args=(self.process.stdout, None), daemon=True)
            t_err = threading.Thread(target=self.read_stream, args=(self.process.stderr, "stderr"), daemon=True)
            t_out.start()
            t_err.start()

        except Exception as e:
            self.append_log(f"\n[ERROR] No se pudo iniciar: {e}\n", "stderr")

    def stop_process(self):
        if not self.is_running or not self.process:
            return

        self.append_log("\n[SISTEMA] Deteniendo proceso...\n", "system")
        self.stop_event.set()
        
        try:
            if sys.platform != "win32":
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
            else:
                self.process.terminate()
            
            self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.process.kill() # Forzar cierre
        except Exception as e:
            self.append_log(f"[ERROR] Error al detener: {e}\n", "stderr")
        
        self.is_running = False
        self.toggle_buttons(running=False)
        self.append_log("[SISTEMA] Proceso detenido.\n", "system")

    def toggle_buttons(self, running):
        if running:
            self.btn_start.config(state=tk.DISABLED, bg="#2d2d2d")
            self.btn_stop.config(state=tk.NORMAL, bg="#c42b1c")
        else:
            self.btn_start.config(state=tk.NORMAL, bg="#3b8640")
            self.btn_stop.config(state=tk.DISABLED, bg="#2d2d2d")


class DashboardApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Panel de Control - Bank Reconciliation")
        self.geometry("1100x700")
        self.configure(bg=BG_COLOR)

        # Estilo para PanedWindow
        style = ttk.Style()
        style.theme_use('default')
        style.configure("TPanedwindow", background=BG_COLOR, sashwidth=5)
        
        # Panel dividido horizontalmente
        paned_window = tk.PanedWindow(self, orient=tk.HORIZONTAL, bg=BG_COLOR, sashwidth=4, sashrelief=tk.RAISED)
        paned_window.pack(fill=tk.BOTH, expand=True)

        # --- Panel Izquierdo: Visualizador Flask ---
        # Detectar el ejecutable de python actual
        python_exe = sys.executable
        self.frame_flask = ProcessTab(paned_window, 
                                      title="🌐 Visualizador Web (Python/Flask)", 
                                      command=[python_exe, "visualizador.py"],
                                      cwd=os.getcwd())
        paned_window.add(self.frame_flask, minsize=400)

        # --- Panel Derecho: Bot WhatsApp ---
        # Asumimos que 'node' está en el PATH.
        self.frame_node = ProcessTab(paned_window, 
                                     title="🤖 WhatsApp Bot (Node.js)", 
                                     command=["node", "bot.js"],
                                     cwd=os.path.join(os.getcwd(), "whatsapp-bot"))
        paned_window.add(self.frame_node, minsize=400)

        # Manejo de cierre de ventana
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def on_close(self):
        if self.frame_flask.is_running:
            self.frame_flask.stop_process()
        if self.frame_node.is_running:
            self.frame_node.stop_process()
        self.destroy()

if __name__ == "__main__":
    app = DashboardApp()
    app.mainloop()
