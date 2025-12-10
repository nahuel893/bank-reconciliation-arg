"""
Módulo del Clasificador de Calidad de Imagen

Utiliza un modelo de lenguaje local para determinar si la calidad
de una imagen de comprobante es 'alta' o 'baja'.
"""
import base64
from openai import OpenAI

def classify_image_quality(image_path: str, client: OpenAI, model_name: str) -> str:
    """
    Clasifica la calidad de una imagen de comprobante.

    Args:
        image_path: Ruta a la imagen.
        client: Cliente de OpenAI configurado para el modelo local.
        model_name: Nombre del modelo a utilizar.

    Returns:
        "alta_calidad", "baja_calidad" o "error".
    """
    try:
        with open(image_path, "rb") as image_file:
            base64_image = base64.b64encode(image_file.read()).decode('utf-8')

        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Eres un experto en analizar la calidad de imágenes de comprobantes de pago. Tu única tarea es determinar si la imagen es de 'alta_calidad' o 'baja_calidad'. Una imagen de alta calidad es aquella que es nítida, legible y no está pixelada o borrosa. Una de baja calidad está borrosa, pixelada, es difícil de leer o es una captura de pantalla de otro dispositivo. Solo puedes responder con 'alta_calidad' o 'baja_calidad'."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=10,
        )

        classification = response.choices[0].message.content.strip().lower()

        if "alta_calidad" in classification:
            return "alta_calidad"
        elif "baja_calidad" in classification:
            return "baja_calidad"
        else:
            return "error"

    except Exception:
        return "error"
