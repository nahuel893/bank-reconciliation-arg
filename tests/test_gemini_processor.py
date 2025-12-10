import pytest
import os
import json
from unittest.mock import MagicMock, patch
from src.gemini_processor import GeminiProcessor
from src.data_models import Comprobante

# --- FIXTURES ---
@pytest.fixture
def mock_gemini_response():
    """Devuelve un objeto respuesta simulado de Gemini."""
    mock_response = MagicMock()
    mock_response.text = """
    ```json
    {
        "banco_emisor": "Mercado Pago",
        "fecha": "27/11/2025",
        "remitente": {
            "nombre_completo": "Juan Perez",
            "identificador": "20-12345678-9",
            "cuenta": "00000031000"
        },
        "destinatario": {
            "nombre_completo": "Comercio Badie",
            "identificador": "30-87654321-0",
            "cuenta": "CVU_DESTINO"
        },
        "monto": "$ 15.000,00",
        "codigo_operacion": "12345ABC"
    }
    ```
    """
    return mock_response

@pytest.fixture
def sample_image_path():
    """Busca una imagen real en el proyecto para pruebas de integración."""
    base_path = "assets/comprobantes-transferencia/alta_calidad"
    if os.path.exists(base_path):
        files = os.listdir(base_path)
        valid_files = [f for f in files if f.endswith(('.jpg', '.jpeg', '.png'))]
        if valid_files:
            return os.path.join(base_path, valid_files[0])
    return None

# --- TESTS ---
def test_procesar_comprobante_mock(mock_gemini_response, tmp_path):
    """
    Prueba que la lógica de mapeo funcione correctamente simulando la respuesta de la API.
    No consume créditos ni requiere internet.
    """
    # Crear una imagen falsa temporal para que PIL.Image.open no falle
    img_path = tmp_path / "test_img.jpg"
    with open(img_path, "wb") as f:
        f.write(b"fake_image_data")

    # Mockear PIL.Image.open para no necesitar una imagen real válida
    with patch("PIL.Image.open") as mock_open:
        # Mockear la API de Gemini
        with patch("google.generativeai.GenerativeModel") as mock_model_cls:
            mock_model_instance = mock_model_cls.return_value
            mock_model_instance.generate_content.return_value = mock_gemini_response
            
            # Instanciar procesador (se mockea configure también si es necesario en __init__)
            with patch("google.generativeai.configure"):
                procesador = GeminiProcessor()
                resultado = procesador.procesar_comprobante(str(img_path))

    # ASERCIONES
    assert isinstance(resultado, Comprobante)
    assert resultado.banco == "Mercado Pago"
    assert resultado.monto == "$ 15.000,00"
    assert resultado.remitente_nombre == "Juan Perez"
    assert resultado.destinatario_nombre == "Comercio Badie"
    assert resultado.id_transferencia == "12345ABC"
    # Verificar que guardó la ruta de la imagen
    assert resultado.imagen_path == str(img_path)

@pytest.mark.integration
def test_procesar_comprobante_real_con_api(sample_image_path):
    """
    Prueba real contra la API de Gemini.
    Requiere una imagen real en assets/ y la API Key configurada.
    """
    if not sample_image_path:
        pytest.skip("No se encontraron imágenes en assets/ para la prueba de integración.")
    
    if not os.getenv("GOOGLE_API_KEY") and not os.path.exists(".env"):
         pytest.skip("No se detectó API KEY de Google.")

    print(f"\nProbando con imagen: {sample_image_path}")
    
    try:
        procesador = GeminiProcessor()
        resultado = procesador.procesar_comprobante(sample_image_path)
        
        # Verificaciones básicas de que algo volvió
        assert isinstance(resultado, Comprobante)
        print(f"\n[Real API] Banco detectado: {resultado.banco}")
        print(f"[Real API] Monto detectado: {resultado.monto}")
        
        # No podemos asegurar el contenido exacto, pero sí que no esté todo vacío
        # (A menos que la imagen sea ilegible, pero asumimos 'alta_calidad')
        # assert resultado.monto is not None 
        
    except Exception as e:
        pytest.fail(f"La prueba de integración falló: {e}")
