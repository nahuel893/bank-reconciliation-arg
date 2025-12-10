const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const axios = require('axios');
const fs = require('fs');
const path = require('path');
const mime = require('mime-types');

// Configuración
const PYTHON_API_URL = 'http://localhost:5000/api/receive-message';
const ASSETS_DIR = path.resolve(__dirname, '../assets/wpp-comprobantes');
const HISTORY_LIMIT = 50; // Cantidad de mensajes hacia atrás a revisar por chat
const TARGET_GROUP_NAME = 'Transferencias Badie'; // <--- EL GRUPO A PROCESAR
const MESSAGE_BUFFER_TIMEOUT = 5 * 60 * 1000; // 5 minutos en milisegundos

// Asegurar que existe el directorio de descarga
if (!fs.existsSync(ASSETS_DIR)){
    fs.mkdirSync(ASSETS_DIR, { recursive: true });
}

// Buffer de mensajes recientes por remitente {sender: [{timestamp, body, messageId}]}
const messageBuffer = new Map();

const client = new Client({
    authStrategy: new LocalAuth(),
    puppeteer: {
        headless: true,
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    }
});

// --- Funciones Auxiliares para el Buffer ---

/**
 * Extrae código numérico de un texto.
 * @param {string} text - El texto del mensaje
 * @returns {string|null} - El código numérico extraído o null
 */
function extractCodigoCliente(text) {
    if (!text || typeof text !== 'string') return null;

    // Buscar secuencias de dígitos
    const matches = text.match(/\d+/g);
    if (matches && matches.length > 0) {
        // Tomar el primer número encontrado (puede ajustarse según necesidad)
        return matches[0];
    }
    return null;
}

/**
 * Agrega un mensaje al buffer de mensajes recientes.
 * @param {string} sender - ID del remitente
 * @param {number} timestamp - Timestamp del mensaje
 * @param {string} body - Cuerpo del mensaje
 * @param {string} messageId - ID del mensaje
 */
function addToBuffer(sender, timestamp, body, messageId) {
    if (!messageBuffer.has(sender)) {
        messageBuffer.set(sender, []);
    }

    const senderMessages = messageBuffer.get(sender);
    senderMessages.push({ timestamp, body, messageId });

    // Limpiar mensajes antiguos (mayores a 5 minutos)
    const now = Date.now();
    const filtered = senderMessages.filter(msg =>
        (now - msg.timestamp * 1000) < MESSAGE_BUFFER_TIMEOUT
    );
    messageBuffer.set(sender, filtered);

    // Limitar el tamaño del buffer por seguridad (últimos 10 mensajes por remitente)
    if (filtered.length > 10) {
        messageBuffer.set(sender, filtered.slice(-10));
    }
}

/**
 * Busca un código de cliente en los mensajes recientes del remitente.
 * @param {string} sender - ID del remitente
 * @param {number} currentTimestamp - Timestamp del mensaje actual
 * @returns {object} - {codigo: string|null, fullMessage: string|null}
 */
function findCodigoInRecentMessages(sender, currentTimestamp) {
    if (!messageBuffer.has(sender)) {
        return { codigo: null, fullMessage: null };
    }

    const senderMessages = messageBuffer.get(sender);
    const now = currentTimestamp * 1000; // Convertir a milisegundos

    // Buscar en mensajes recientes (dentro de 5 minutos hacia adelante)
    for (const msg of senderMessages) {
        const msgTime = msg.timestamp * 1000;
        const timeDiff = msgTime - now;

        // Solo mensajes posteriores al actual y dentro de la ventana de 5 min
        if (timeDiff > 0 && timeDiff < MESSAGE_BUFFER_TIMEOUT) {
            const codigo = extractCodigoCliente(msg.body);
            if (codigo) {
                return { codigo, fullMessage: msg.body };
            }
        }
    }

    return { codigo: null, fullMessage: null };
}

// --- Función Principal de Procesamiento ---
async function processMessage(msg) {
    const chat = await msg.getChat();

    // Filtrar: Solo procesar si es del grupo objetivo
    if (!chat.isGroup || chat.name !== TARGET_GROUP_NAME) {
        return;
    }

    // Agregar todos los mensajes de texto al buffer
    if (msg.body && msg.body.trim() !== '') {
        addToBuffer(msg.from, msg.timestamp, msg.body, msg.id._serialized);
    }

    if (msg.hasMedia) {
        try {
            const media = await msg.downloadMedia();

            if (!media) {
                console.log(`[${msg.id._serialized}] No se pudo descargar el medio.`);
                return;
            }

            // Generar nombre de archivo único usando timestamp y ID de mensaje para evitar colisiones
            const extension = mime.extension(media.mimetype) || 'jpg';
            // Limpiar ID para nombre de archivo
            const safeId = msg.id._serialized.replace(/[^a-zA-Z0-9]/g, '_');
            const filename = `wpp_${msg.timestamp}_${safeId}.${extension}`;
            const filepath = path.join(ASSETS_DIR, filename);

            // Guardar archivo (sobrescribir si existe está bien, es el mismo archivo)
            fs.writeFileSync(filepath, media.data, 'base64');

            // Intentar extraer código de cliente
            let codigoCliente = null;
            let mensajeCompleto = msg.body || '';

            // 1. Primero intentar extraer del body del mensaje con imagen
            codigoCliente = extractCodigoCliente(msg.body);

            // 2. Si no se encuentra, buscar en mensajes recientes del mismo remitente
            if (!codigoCliente) {
                const bufferResult = findCodigoInRecentMessages(msg.from, msg.timestamp);
                if (bufferResult.codigo) {
                    codigoCliente = bufferResult.codigo;
                    mensajeCompleto = bufferResult.fullMessage;
                    console.log(`[INFO] Código ${codigoCliente} encontrado en mensaje posterior del remitente`);
                }
            }

            // 3. Si aún no se encuentra, usar "DESCONOCIDO"
            if (!codigoCliente) {
                codigoCliente = 'DESCONOCIDO';
                console.log(`[WARN] No se encontró código de cliente para ${msg.id._serialized}, usando DESCONOCIDO`);
            }

            // Enviar metadatos a Python
            const payload = {
                id: msg.id._serialized,
                sender: msg.from,
                timestamp: msg.timestamp,
                body: mensajeCompleto,
                image_path: filepath,
                has_media: true,
                cliente_codigo: codigoCliente
            };

            const response = await axios.post(PYTHON_API_URL, payload);
            if (response.data.status === 'skipped') {
                console.log(`[INFO] Mensaje ${msg.id._serialized} ya estaba procesado.`);
            } else {
                console.log(`[EXITO] Nuevo comprobante procesado: ${msg.id._serialized}, Cliente: ${codigoCliente}`);
            }

        } catch (error) {
            let errorMsg = error.message;

            if (axios.isAxiosError(error)) {
                if (error.response) {
                    errorMsg = `Python Server Error (${error.response.status}): ${JSON.stringify(error.response.data)}`;
                } else if (error.request) {
                    errorMsg = "No response received from Python server (Is it running?)";
                } else {
                    errorMsg = `Axios Request Error: ${error.message}`;
                }
            } else {
                console.error(`[Stack Trace]`, error.stack);
            }

            console.error(`[ERROR] Falló procesamiento de ${msg.id._serialized}: ${errorMsg}`);
        }
    }
}

// --- Función de Sincronización Histórica ---
async function syncRecentMessages() {
    console.log('--- Iniciando Sincronización de Historial ---');
    const chats = await client.getChats();
    console.log(`Encontrados ${chats.length} chats activos.`);

    for (const chat of chats) {
        // Filtrar aquí también para no pedir mensajes de chats no objetivo
        if (!chat.isGroup || chat.name !== TARGET_GROUP_NAME) {
            continue;
        }

        console.log(`Revisando chat: ${chat.name}...`);
        try {
            const messages = await chat.fetchMessages({ limit: HISTORY_LIMIT });

            // Primero, agregar todos los mensajes al buffer (para construir el contexto)
            console.log(`Construyendo buffer de mensajes...`);
            for (const msg of messages) {
                if (msg.body && msg.body.trim() !== '') {
                    addToBuffer(msg.from, msg.timestamp, msg.body, msg.id._serialized);
                }
            }

            // Luego, procesar mensajes con media
            console.log(`Procesando comprobantes...`);
            for (const msg of messages) {
                if (msg.hasMedia) {
                    await processMessage(msg);
                }
            }
        } catch (err) {
            console.error(`Error leyendo chat ${chat.name}: ${err.message}`);
        }
    }
    console.log('--- Sincronización Finalizada ---');
}


// --- Eventos del Cliente ---

client.on('qr', (qr) => {
    qrcode.generate(qr, { small: true });
    console.log('ESCANEA ESTE CODIGO QR CON TU WHATSAPP');
});

client.on('ready', async () => {
    console.log('Cliente de WhatsApp listo.');
    // Iniciar sincronización de mensajes antiguos
    await syncRecentMessages();
    console.log('Escuchando nuevos mensajes en tiempo real...');
});

client.on('message_create', async (msg) => {
    // Procesar mensajes nuevos en tiempo real
    await processMessage(msg);
});

client.initialize();
