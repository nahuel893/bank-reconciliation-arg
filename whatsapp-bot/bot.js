const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const axios = require('axios');
const fs = require('fs');
const path = require('path');
const mime = require('mime-types');

// Configuración
const PYTHON_API_URL = 'http://localhost:5000/api/receive-message';
const ASSETS_DIR = path.resolve(__dirname, '../assets/wpp-comprobantes');
const HISTORY_LIMIT = 500; // Cantidad de mensajes hacia atrás a revisar por chat
const TARGET_GROUP_NAME = 'Transferencias Badie'; // <--- EL GRUPO A PROCESAR
const NEXT_MESSAGE_TIMEOUT = 60 * 1000; // 1 minuto para esperar el siguiente mensaje (tiempo real)
const HISTORICAL_MAX_TIME_DIFF = 60; // 1 minuto máximo entre imagen y siguiente mensaje (histórico, en segundos)

// === CONFIGURACIÓN DE DEBUG ===
// Activar con: DEBUG=true node bot.js
// O modificar directamente aquí
const DEBUG_MODE = process.env.DEBUG === 'true' || false;
const LOG_FILE = path.resolve(__dirname, 'bot_debug.log');

// Logger con niveles y archivo
const Logger = {
    _write(level, ...args) {
        const timestamp = new Date().toISOString();
        const message = args.map(a => typeof a === 'object' ? JSON.stringify(a, null, 2) : a).join(' ');
        const line = `[${timestamp}] [${level}] ${message}`;

        console.log(line);

        if (DEBUG_MODE) {
            fs.appendFileSync(LOG_FILE, line + '\n');
        }
    },
    info(...args) { this._write('INFO', ...args); },
    warn(...args) { this._write('WARN', ...args); },
    error(...args) { this._write('ERROR', ...args); },
    debug(...args) {
        if (DEBUG_MODE) {
            this._write('DEBUG', ...args);
        }
    },
    // Log especial para asociaciones imagen-código (siempre visible)
    match(imageId, codigo, source, details = {}) {
        const info = {
            imagen: imageId,
            codigo: codigo,
            fuente: source, // 'body', 'mismo_timestamp', 'siguiente_mensaje', 'timeout'
            ...details
        };
        this._write('MATCH', JSON.stringify(info));
    }
};

// Asegurar que existe el directorio de descarga
if (!fs.existsSync(ASSETS_DIR)){
    fs.mkdirSync(ASSETS_DIR, { recursive: true });
}

// Cola de imágenes esperando el siguiente mensaje del autor
// Estructura: {author: {imageData, timeoutId}}
const waitingForNextMessage = new Map();

const client = new Client({
    authStrategy: new LocalAuth(),
    puppeteer: {
        headless: true,
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    }
});

// --- Funciones Auxiliares ---

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
        // Tomar el primer número encontrado
        return matches[0];
    }
    return null;
}

/**
 * Obtiene el identificador del autor real del mensaje.
 * En grupos, msg.from es el grupo, msg.author es el usuario.
 * En chats privados, msg.from es el usuario y msg.author es undefined.
 * @param {object} msg - Objeto mensaje de WhatsApp
 * @returns {string} - ID del autor real
 */
function getMessageAuthor(msg) {
    return msg.author || msg.from;
}

/**
 * Envía una imagen al backend Python para procesamiento.
 * @param {object} imageData - Datos de la imagen a procesar
 * @param {string} codigoCliente - Código de cliente a asignar
 * @param {string} mensajeCompleto - Mensaje completo (body del código)
 */
async function sendImageToBackend(imageData, codigoCliente, mensajeCompleto, matchSource = 'unknown') {
    const payload = {
        id: imageData.messageId,
        sender: imageData.sender,
        author: imageData.author,
        timestamp: imageData.timestamp,
        body: mensajeCompleto,
        image_path: imageData.filepath,
        has_media: true,
        cliente_codigo: codigoCliente
    };

    Logger.debug('Enviando a backend:', payload);

    try {
        const response = await axios.post(PYTHON_API_URL, payload);
        if (response.data.status === 'skipped') {
            Logger.info(`Mensaje ${imageData.messageId} ya estaba procesado.`);
        } else {
            Logger.info(`Comprobante procesado: ${imageData.messageId}, Cliente: ${codigoCliente}`);
            Logger.match(imageData.messageId, codigoCliente, matchSource, {
                autor: imageData.author,
                timestamp: imageData.timestamp,
                body: mensajeCompleto?.substring(0, 50)
            });
        }
        return true;
    } catch (error) {
        let errorMsg = error.message;
        if (axios.isAxiosError(error)) {
            if (error.response) {
                errorMsg = `Python Server Error (${error.response.status}): ${JSON.stringify(error.response.data)}`;
            } else if (error.request) {
                errorMsg = "No response received from Python server (Is it running?)";
            }
        }
        Logger.error(`Falló procesamiento de ${imageData.messageId}: ${errorMsg}`);
        return false;
    }
}

/**
 * Procesa la imagen en espera como DESCONOCIDO cuando expira el timeout.
 * @param {string} author - ID del autor
 */
async function processWaitingImageAsUnknown(author) {
    if (!waitingForNextMessage.has(author)) return;

    const waiting = waitingForNextMessage.get(author);
    Logger.warn(`Timeout expirado. Procesando imagen de ${author} como DESCONOCIDO`);

    await sendImageToBackend(waiting.imageData, 'DESCONOCIDO', '', 'timeout');
    waitingForNextMessage.delete(author);
}

/**
 * Registra una imagen para esperar el siguiente mensaje del autor.
 * @param {string} author - ID del autor
 * @param {object} imageData - Datos de la imagen
 */
function waitForNextMessage(author, imageData) {
    // Si ya hay una imagen esperando de este autor, procesarla como DESCONOCIDO primero
    if (waitingForNextMessage.has(author)) {
        const existing = waitingForNextMessage.get(author);
        clearTimeout(existing.timeoutId);
        Logger.warn(`Autor ${author} envió otra imagen antes del código. Procesando anterior como DESCONOCIDO`);
        sendImageToBackend(existing.imageData, 'DESCONOCIDO', '', 'imagen_sin_codigo');
    }

    const timeoutId = setTimeout(async () => {
        await processWaitingImageAsUnknown(author);
    }, NEXT_MESSAGE_TIMEOUT);

    waitingForNextMessage.set(author, { imageData, timeoutId });
    Logger.info(`Esperando siguiente mensaje de ${author} (timeout: ${NEXT_MESSAGE_TIMEOUT/1000}s)`);
    Logger.debug('Imagen en espera:', { messageId: imageData.messageId, timestamp: imageData.timestamp });
}

/**
 * Procesa un mensaje de WhatsApp.
 *
 * Lógica simplificada:
 * - Si llega una imagen CON código en body → procesa inmediatamente
 * - Si llega una imagen SIN código → espera el siguiente mensaje del mismo autor
 * - Si llega un mensaje de texto y hay imagen esperando → usa el código y procesa
 * - Si pasa el timeout → procesa como DESCONOCIDO
 *
 * @param {object} msg - Mensaje de WhatsApp
 * @param {object} options - Opciones de procesamiento
 * @param {object} options.chat - Chat pre-obtenido (opcional)
 * @param {boolean} options.isHistorical - Si es procesamiento histórico
 * @param {object} options.nextMessage - Siguiente mensaje (solo para histórico)
 */
async function processMessage(msg, options = {}) {
    const { chat: preloadedChat, isHistorical = false, nextMessage = null } = options;

    // Usar chat pre-cargado o obtenerlo
    const chat = preloadedChat || await msg.getChat();

    // Filtrar: Solo procesar si es del grupo objetivo
    if (!chat.isGroup || chat.name !== TARGET_GROUP_NAME) {
        return;
    }

    const author = getMessageAuthor(msg);

    // En tiempo real: si llega un mensaje de texto y hay imagen esperando de este autor
    if (!isHistorical && !msg.hasMedia && msg.body && waitingForNextMessage.has(author)) {
        const codigo = extractCodigoCliente(msg.body);
        if (codigo) {
            const waiting = waitingForNextMessage.get(author);
            clearTimeout(waiting.timeoutId);

            Logger.info(`Código ${codigo} recibido en tiempo real, procesando imagen en espera...`);
            Logger.debug('Mensaje de código:', { body: msg.body, timestamp: msg.timestamp });
            await sendImageToBackend(waiting.imageData, codigo, msg.body, 'tiempo_real');
            waitingForNextMessage.delete(author);
        }
        return;
    }

    if (msg.hasMedia) {
        try {
            Logger.debug(`Procesando imagen: ${msg.id._serialized}`, {
                autor: author,
                timestamp: msg.timestamp,
                body: msg.body || '(sin body)',
                isHistorical
            });

            const media = await msg.downloadMedia();

            if (!media) {
                Logger.warn(`No se pudo descargar el medio: ${msg.id._serialized}`);
                return;
            }

            // Generar nombre de archivo único
            const extension = mime.extension(media.mimetype) || 'jpg';
            const safeId = msg.id._serialized.replace(/[^a-zA-Z0-9]/g, '_');
            const filename = `wpp_${msg.timestamp}_${safeId}.${extension}`;
            const filepath = path.join(ASSETS_DIR, filename);

            // Guardar archivo
            fs.writeFileSync(filepath, media.data, 'base64');
            Logger.debug(`Imagen guardada: ${filename}`);

            const imageData = {
                messageId: msg.id._serialized,
                sender: msg.from,
                author: author,
                timestamp: msg.timestamp,
                filepath: filepath
            };

            // 1. Intentar extraer código del body del mensaje con imagen
            const codigoEnBody = extractCodigoCliente(msg.body);

            if (codigoEnBody) {
                // Imagen tiene código en body → procesar inmediatamente
                Logger.info(`Código ${codigoEnBody} encontrado en body de la imagen`);
                await sendImageToBackend(imageData, codigoEnBody, msg.body, 'body_imagen');

            } else if (isHistorical) {
                // Modo histórico: usar el siguiente mensaje si fue proporcionado
                if (nextMessage) {
                    const codigoNext = extractCodigoCliente(nextMessage.body);
                    const matchSource = nextMessage.timestamp === msg.timestamp ? 'mismo_timestamp' : 'siguiente_mensaje';
                    if (codigoNext) {
                        Logger.info(`Código ${codigoNext} encontrado (${matchSource})`);
                        Logger.debug('Mensaje asociado:', {
                            body: nextMessage.body,
                            timestamp: nextMessage.timestamp,
                            timeDiff: nextMessage.timestamp - msg.timestamp
                        });
                        await sendImageToBackend(imageData, codigoNext, nextMessage.body, matchSource);
                    } else {
                        Logger.warn(`Siguiente mensaje sin código numérico para ${msg.id._serialized}`);
                        Logger.debug('Mensaje rechazado:', { body: nextMessage.body });
                        await sendImageToBackend(imageData, 'DESCONOCIDO', '', 'mensaje_sin_codigo');
                    }
                } else {
                    Logger.warn(`No hay siguiente mensaje para ${msg.id._serialized}, usando DESCONOCIDO`);
                    await sendImageToBackend(imageData, 'DESCONOCIDO', '', 'sin_mensaje_siguiente');
                }

            } else {
                // Tiempo real sin código: esperar el siguiente mensaje
                Logger.info(`Imagen sin código en body, esperando siguiente mensaje...`);
                waitForNextMessage(author, imageData);
            }

        } catch (error) {
            let errorMsg = error.message;
            if (axios.isAxiosError(error)) {
                if (error.response) {
                    errorMsg = `Python Server Error (${error.response.status}): ${JSON.stringify(error.response.data)}`;
                } else if (error.request) {
                    errorMsg = "No response received from Python server (Is it running?)";
                }
            } else {
                Logger.debug('Stack Trace:', error.stack);
            }
            Logger.error(`Falló procesamiento de ${msg.id._serialized}: ${errorMsg}`);
        }
    }
}

// --- Función de Sincronización Histórica ---
async function syncRecentMessages() {
    Logger.info('=== Iniciando Sincronización de Historial ===');
    const chats = await client.getChats();
    Logger.info(`Encontrados ${chats.length} chats activos.`);

    for (const chat of chats) {
        if (!chat.isGroup || chat.name !== TARGET_GROUP_NAME) {
            continue;
        }

        Logger.info(`Revisando chat: ${chat.name}...`);
        try {
            const messages = await chat.fetchMessages({ limit: HISTORY_LIMIT });

            // Ordenar mensajes por timestamp, preservando orden original para mismo timestamp (sort estable)
            // Guardamos el índice original para desempatar
            messages.forEach((msg, idx) => msg._originalIndex = idx);
            messages.sort((a, b) => {
                const timeDiff = a.timestamp - b.timestamp;
                if (timeDiff !== 0) return timeDiff;
                // Si mismo timestamp, preservar orden original de WhatsApp
                return a._originalIndex - b._originalIndex;
            });

            // Procesar mensajes con media
            const mediaMessages = messages.filter(m => m.hasMedia);
            Logger.info(`Procesando ${mediaMessages.length} comprobantes de ${messages.length} mensajes...`);

            // Set para rastrear mensajes de texto ya usados como código
            const usedTextMessages = new Set();

            for (let i = 0; i < messages.length; i++) {
                const msg = messages[i];

                if (!msg.hasMedia) continue;

                const author = getMessageAuthor(msg);

                // Buscar el mensaje de texto asociado del mismo autor
                // IMPORTANTE: WhatsApp puede devolver texto y imagen con mismo timestamp
                // en cualquier orden, así que buscamos:
                // 1. Hacia adelante: textos con MISMO timestamp (imagen llegó antes que texto)
                // 2. Hacia atrás: textos con MISMO timestamp (texto llegó antes que imagen)
                // 3. Hacia adelante: textos dentro del tiempo límite (timestamps diferentes)
                let nextMessage = null;

                // 1. Buscar HACIA ADELANTE con MISMO timestamp
                // (caso más común: imagen llega antes que texto pero ambos tienen mismo timestamp)
                for (let j = i + 1; j < messages.length; j++) {
                    const candidate = messages[j];

                    // Si ya pasamos a otro timestamp, dejamos de buscar
                    if (candidate.timestamp > msg.timestamp) {
                        break;
                    }

                    // Saltar mensajes ya usados
                    if (usedTextMessages.has(candidate.id._serialized)) {
                        continue;
                    }

                    if (getMessageAuthor(candidate) === author &&
                        !candidate.hasMedia &&
                        candidate.body) {
                        nextMessage = candidate;
                        usedTextMessages.add(candidate.id._serialized);
                        break;
                    }
                }

                // 2. Si no encontramos, buscar HACIA ATRÁS con MISMO timestamp
                // (caso: WhatsApp devolvió texto antes que imagen)
                if (!nextMessage) {
                    for (let j = i - 1; j >= 0; j--) {
                        const candidate = messages[j];

                        // Si ya pasamos a otro timestamp, dejamos de buscar hacia atrás
                        if (candidate.timestamp < msg.timestamp) {
                            break;
                        }

                        // Saltar mensajes ya usados
                        if (usedTextMessages.has(candidate.id._serialized)) {
                            continue;
                        }

                        if (getMessageAuthor(candidate) === author &&
                            !candidate.hasMedia &&
                            candidate.body &&
                            candidate.timestamp === msg.timestamp) {
                            nextMessage = candidate;
                            usedTextMessages.add(candidate.id._serialized);
                            break;
                        }
                    }
                }

                // 3. Si no encontramos, buscar HACIA ADELANTE dentro del tiempo límite
                if (!nextMessage) {
                    for (let j = i + 1; j < messages.length; j++) {
                        const candidate = messages[j];

                        // Saltar mensajes ya usados
                        if (usedTextMessages.has(candidate.id._serialized)) {
                            continue;
                        }

                        if (getMessageAuthor(candidate) === author) {
                            // Es un mensaje del mismo autor
                            const timeDiff = candidate.timestamp - msg.timestamp;

                            if (candidate.hasMedia) {
                                // Si es otra imagen del mismo autor, detenemos la búsqueda
                                // (el código debe estar entre esta imagen y la siguiente)
                                break;
                            }

                            if (candidate.body && timeDiff <= HISTORICAL_MAX_TIME_DIFF) {
                                nextMessage = candidate;
                                // Marcar como usado para que no se reutilice
                                usedTextMessages.add(candidate.id._serialized);
                                break;
                            }
                        }
                    }
                }

                await processMessage(msg, { chat, isHistorical: true, nextMessage });
            }
        } catch (err) {
            Logger.error(`Error leyendo chat ${chat.name}: ${err.message}`);
        }
    }
    Logger.info('=== Sincronización Finalizada ===');
}


// --- Eventos del Cliente ---

client.on('qr', (qr) => {
    qrcode.generate(qr, { small: true });
    Logger.info('ESCANEA ESTE CODIGO QR CON TU WHATSAPP');
});

client.on('ready', async () => {
    Logger.info('Cliente de WhatsApp listo.');
    Logger.info(`DEBUG_MODE: ${DEBUG_MODE ? 'ACTIVADO' : 'desactivado'}`);
    if (DEBUG_MODE) {
        Logger.info(`Los logs se guardan en: ${LOG_FILE}`);
    }
    await syncRecentMessages();
    Logger.info('Escuchando nuevos mensajes en tiempo real...');
});

client.on('message_create', async (msg) => {
    await processMessage(msg);
});

client.initialize();
