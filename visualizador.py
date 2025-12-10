from flask import Flask, render_template, request, jsonify
import os
from src.database import SessionLocal
from src.data_models import Comprobante, Mensaje
from src.gemini_processor import GeminiProcessor

app = Flask(__name__, static_folder='assets')
IMAGE_DIR = os.path.join('assets', 'wpp-comprobantes')

def get_db_data():
    """Obtiene los datos de la base de datos."""
    db = SessionLocal()
    try:
        comprobantes = db.query(Comprobante).order_by(Comprobante.id.desc()).all()
        # Convertir los objetos SQLAlchemy a diccionarios
        data = []
        for c in comprobantes:
            item = c.__dict__.copy()
            item.pop('_sa_instance_state', None) # Eliminar estado de SQLAlchemy
            
            # Extraer solo el nombre del archivo para usar en el template
            if item.get('imagen_path'):
                item['filename'] = os.path.basename(item['imagen_path'])
            else:
                item['filename'] = None
                
            data.append(item)
        return data
    finally:
        db.close()

@app.route('/')
def home():
    images = []
    if os.path.exists(IMAGE_DIR):
        images = sorted([f for f in os.listdir(IMAGE_DIR) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))])
    
    data = get_db_data()

    return render_template('index.html', images=images, data=data)

@app.route('/api/receive-message', methods=['POST'])
def receive_message():
    """Recibe mensajes del bot de WhatsApp."""
    data = request.json
    if not data:
        return jsonify({"error": "No data received"}), 400

    message_id = data.get('id')
    sender = data.get('sender')
    body = data.get('body', '')
    cliente_codigo = data.get('cliente_codigo', 'DESCONOCIDO')

    # Validación de duplicados
    db = SessionLocal()
    try:
        if message_id:
            existe = db.query(Mensaje).filter_by(message_id=message_id).first()
            if existe:
                print(f"Mensaje {message_id} ya procesado previamente. Saltando.")
                return jsonify({"status": "skipped", "message": "Message already processed"}), 200
    except Exception as e:
        print(f"Error verificando duplicados: {e}")
    finally:
        db.close()

    print(f"Nuevo mensaje recibido de {sender}, Cliente: {cliente_codigo}")

    if data.get('has_media') and data.get('image_path'):
        image_path = data.get('image_path')

        # Verificar que la imagen existe
        if not os.path.exists(image_path):
             return jsonify({"error": f"Image file not found at {image_path}"}), 404

        try:
            # Procesar con Gemini
            print(f"Procesando imagen: {image_path}")
            processor = GeminiProcessor()
            comprobante = processor.procesar_comprobante(image_path)

            # Guardar en BD con relación al Mensaje
            db = SessionLocal()
            try:
                # 1. Crear el Mensaje
                nuevo_mensaje = Mensaje(
                    message_id=message_id if message_id else "unknown",
                    timestamp=None,  # Podrías parsear el timestamp si lo envías formateado
                    sender=sender,
                    body=body
                )
                db.add(nuevo_mensaje)
                db.flush() # Para obtener el ID del mensaje

                # 2. Asignar el ID del mensaje y código de cliente al comprobante
                comprobante.mensaje_id = nuevo_mensaje.id
                comprobante.cliente_codigo = cliente_codigo
                db.add(comprobante)

                db.commit()
                print(f"Comprobante guardado en BD: ID {comprobante.id}, Cliente: {cliente_codigo}")
                return jsonify({"status": "success", "message": "Comprobante procesado y guardado", "id": comprobante.id, "cliente_codigo": cliente_codigo}), 201
            except Exception as e:
                db.rollback()
                print(f"Error guardando en BD: {e}")
                return jsonify({"error": str(e)}), 500
            finally:
                db.close()

        except Exception as e:
            print(f"Error procesando con Gemini: {e}")
            return jsonify({"error": str(e)}), 500

    return jsonify({"status": "ignored", "message": "No media or image path provided"}), 200

if __name__ == '__main__':
    print("Iniciando el servidor web...")
    print(f"Visita http://127.0.0.1:5000 en tu navegador.")
    app.run(debug=True, host='0.0.0.0')