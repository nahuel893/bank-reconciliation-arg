import pytest
from unittest.mock import patch
from src.main import process_new_message
from datetime import datetime
from src.data_models import Comprobante, Mensaje

def test_process_new_message_saves_to_db(db_session):
    # Mock data simulating a new message
    mock_message_data = {
        "id": {"id": "12345"},
        "body": "Hi there!",
        "timestamp": 1678886400,
        "hasMedia": True,
        "media": {
            "mimetype": "image/jpeg",
                            "data": "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"        }
    }

    # Mock Gemini Processor
    with patch('src.gemini_processor.GeminiProcessor.procesar_comprobante') as mock_process_comprobante:
        mock_process_comprobante.return_value = Comprobante(
            banco="Test Bank",
            monto=100.0,
            fecha_transferencia=datetime.now(),
            id_transferencia="test-id",
            detalle="Test transfer"
        )

        # Process the message
        process_new_message(mock_message_data, db_session)

        # Verify data is in the database
        mensaje = db_session.query(Mensaje).filter_by(message_id="12345").first()
        assert mensaje is not None
        
        result = db_session.query(Comprobante).filter_by(mensaje_id=mensaje.id, id_transferencia="test-id").first()
        assert result is not None
        assert result.banco == "Test Bank"
        assert result.monto == 100.0