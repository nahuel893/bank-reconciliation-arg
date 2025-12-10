"""
Módulo del Procesador Gemini

Contiene la lógica para interactuar con la API de Gemini,
enviar las imágenes de los comprobantes y procesar la respuesta.
"""
import json
import re
from typing import Dict, Any

import google.generativeai as genai
from PIL import Image

from src.config import settings
from src.data_models import Comprobante


class GeminiProcessor:
    """
    Gestiona la comunicación con la API de Google Gemini para extraer
    información de imágenes de comprobantes.
    """
    def __init__(self):
        """Inicializa el procesador configurando la API de Gemini."""
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel('gemini-2.5-flash')
        self.prompt = self._construir_prompt()

    def _construir_prompt(self) -> str:
        """
        Construye el prompt detallado que se enviará al modelo.
        """
        return """
        Eres un experto en análisis de documentos financieros de Argentina.
        Tu tarea es extraer información clave de la imagen de un comprobante de transferencia.
        Analiza la imagen y devuelve un objeto JSON con la siguiente estructura y campos.
        Si un campo no se puede encontrar, su valor debe ser null.

        {
          "banco_emisor": "Nombre del banco o billetera virtual que emite el comprobante (ej: Mercado Pago, Ualá, Banco Galicia).",
          "fecha": "Fecha del comprobante. Convierte la fecha en formato YYYY/MM/DD"
          "remitente": {
            "nombre_completo": "Nombre completo de la persona que envía el dinero.",
            "identificador": "CUIT, CUIL o DNI de la persona que envía.",
            "cuenta": "CBU, CVU o Alias de la cuenta desde la que se envía."
          },
          "destinatario": {
            "nombre_completo": "Nombre completo de la persona que recibe el dinero.",
            "identificador": "CUIT, CUIL o DNI de la persona que recibe.",
            "cuenta": "CBU, CVU o Alias de la cuenta que recibe el dinero."
          },
          "monto": "Monto total transferido, como un string (ej: '$ 10.500,00').",
          "codigo_operacion": "El código único de la transacción (ej: N° de Operación, Código de Identificación, etc.)."
        }
        """

    def _limpiar_monto(self, monto_raw: Any) -> str:
        """
        Limpia el string de monto para convertirlo a un formato numérico estándar (string).
        Maneja formato argentino (1.000,00) y lo convierte a estándar (1000.00).
        """
        if not monto_raw:
            return None
        
        # Convertir a string y limpiar espacios
        s = str(monto_raw).strip()
        
        # Eliminar símbolos de moneda y caracteres no numéricos excepto puntos y comas
        # Mantenemos dígitos, '.', ',' y '-' (por si acaso negativos)
        s = re.sub(r'[^\d.,\-]', '', s)
        
        if not s:
            return None

        # Lógica de detección de formato
        if '.' in s and ',' in s:
            # Si el punto está antes (1.500,00) -> ARG/EUR
            if s.find('.') < s.find(','):
                s = s.replace('.', '').replace(',', '.')
            # Si la coma está antes (1,500.00) -> US
            else:
                s = s.replace(',', '')
        elif ',' in s:
            # Solo coma (500,50) -> Asumimos decimal ARG
            s = s.replace(',', '.')
        elif '.' in s:
            # Solo puntos.
            # Caso dificil: 1.500 (mil quinientos) vs 10.50 (diez con cincuenta).
            # En comprobantes ARG, 1.000 suele ser mil.
            # Si hay más de un punto (1.000.000), seguro es separador de miles.
            if s.count('.') > 1:
                s = s.replace('.', '')
            else:
                # Si tiene 3 decimales (1.500), asumimos miles.
                # Si tiene 2 (10.50), asumimos decimal.
                parts = s.split('.')
                if len(parts[-1]) == 3:
                    s = s.replace('.', '')
                # De lo contrario dejamos el punto como decimal
        
        return s

    def _mapear_a_comprobante(self, datos: Dict[str, Any], ruta_imagen: str) -> Comprobante:
        """
        Mapea el diccionario de datos extraídos a un objeto Comprobante de SQLAlchemy.
        """
        remitente_data = datos.get("remitente", {}) or {}
        destinatario_data = datos.get("destinatario", {}) or {}

        # Asegurar que si el sub-objeto es None, no falle el .get
        if remitente_data is None: remitente_data = {}
        if destinatario_data is None: destinatario_data = {}
        
        monto_limpio = self._limpiar_monto(datos.get("monto"))

        return Comprobante(
            imagen_path=ruta_imagen,
            fecha_transferencia=datos.get("fecha"),
            banco=datos.get("banco_emisor"),
            monto=monto_limpio,
            id_transferencia=datos.get("codigo_operacion"),
            
            remitente_nombre=remitente_data.get("nombre_completo"),
            remitente_id=remitente_data.get("identificador"),
            remitente_cuenta=remitente_data.get("cuenta"),
            
            destinatario_nombre=destinatario_data.get("nombre_completo"),
            destinatario_id=destinatario_data.get("identificador"),
            destinatario_cuenta=destinatario_data.get("cuenta"),
        )

    def procesar_comprobante(self, ruta_imagen: str) -> Comprobante:
        """
        Abre una imagen, la envía a la API de Gemini y parsea la respuesta.

        Args:
            ruta_imagen (str): La ruta al archivo de imagen del comprobante.

        Returns:
            Comprobante: Un objeto con la información extraída.
            
        Raises:
            FileNotFoundError: Si la ruta de la imagen no es válida.
            Exception: Para otros errores durante el procesamiento de la API.
        """
        try:
            img = Image.open(ruta_imagen)
        except FileNotFoundError:
            print(f"Error: No se pudo encontrar la imagen en la ruta: {ruta_imagen}")
            raise

        try:
            response = self.model.generate_content([self.prompt, img])
            
            # Limpiar y parsear la respuesta JSON
            raw_json = response.text.strip().replace("`", "").replace("json", "")
            datos_extraidos = json.loads(raw_json)

            return self._mapear_a_comprobante(datos_extraidos, ruta_imagen)
        
        except Exception as e:
            print(f"Error al procesar la imagen con Gemini: {e}")
            # Devolver un comprobante vacío en caso de error para no detener el flujo
            return Comprobante(imagen_path=ruta_imagen)
