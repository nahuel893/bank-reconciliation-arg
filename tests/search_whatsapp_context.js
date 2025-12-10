/**
 * Script para Buscar Contexto en WhatsApp
 *
 * Dado un message_id, busca el mensaje en WhatsApp y muestra el contexto:
 * - El mensaje en sí
 * - Mensajes anteriores y posteriores del mismo autor
 * - Ayuda a entender por qué quedó como DESCONOCIDO
 *
 * Uso:
 *   node tests/search_whatsapp_context.js <message_id>
 *   node tests/search_whatsapp_context.js --list-desconocidos
 *   node tests/search_whatsapp_context.js --analyze-all
 *
 * Ejemplos:
 *   node tests/search_whatsapp_context.js true_123456789@g.us_ABC123
 *   node tests/search_whatsapp_context.js --list-desconocidos
 */

const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const { Pool } = require('pg');
const path = require('path');

// Configuración
const HISTORY_LIMIT = 1000;
const TARGET_GROUP_NAME = 'Transferencias Badie';
const CONTEXT_MESSAGES = 5; // Mensajes antes/después a mostrar

// Configuración de PostgreSQL (ajustar según tu .env)
const pool = new Pool({
    connectionString: process.env.DATABASE_URL || 'postgresql://postgres:postgres@localhost:5432/comprobantes'
});

const client = new Client({
    authStrategy: new LocalAuth(),
    puppeteer: {
        headless: true,
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    }
});

function getMessageAuthor(msg) {
    return msg.author || msg.from;
}

function formatTimestamp(timestamp) {
    return new Date(timestamp * 1000).toLocaleString('es-AR');
}

function extractCodigoCliente(text) {
    if (!text || typeof text !== 'string') return null;
    const matches = text.match(/\d+/g);
    return matches ? matches[0] : null;
}

async function getDesconocidosFromDB() {
    """Obtiene los message_id de comprobantes DESCONOCIDO desde la BD."""
    try {
        const result = await pool.query(`
            SELECT m.message_id, m.author, m.timestamp, c.imagen_path
            FROM comprobantes c
            JOIN mensajes m ON c.mensaje_id = m.id
            WHERE c.cliente_codigo = 'DESCONOCIDO'
            ORDER BY c.id DESC
        `);
        return result.rows;
    } catch (error) {
        console.error('Error conectando a la BD:', error.message);
        console.log('Asegúrate de que DATABASE_URL esté configurado correctamente.');
        return [];
    }
}

async function searchMessageContext(messages, targetMessageId) {
    """Busca un mensaje y muestra su contexto."""
    console.log(`\nBuscando mensaje: ${targetMessageId}`);
    console.log('-'.repeat(80));

    // Encontrar el mensaje objetivo
    const targetIndex = messages.findIndex(m => m.id._serialized === targetMessageId);

    if (targetIndex === -1) {
        console.log('❌ Mensaje no encontrado en el historial');
        console.log('   Puede que el mensaje sea muy antiguo o haya sido eliminado.');
        return false;
    }

    const targetMsg = messages[targetIndex];
    const author = getMessageAuthor(targetMsg);

    console.log('\n📌 MENSAJE OBJETIVO:');
    console.log(`   ID: ${targetMsg.id._serialized}`);
    console.log(`   Author: ${author}`);
    console.log(`   Timestamp: ${formatTimestamp(targetMsg.timestamp)}`);
    console.log(`   Has Media: ${targetMsg.hasMedia ? 'SÍ' : 'NO'}`);
    console.log(`   Body: "${targetMsg.body || '(vacío)'}"`);

    // Filtrar mensajes del mismo autor
    const authorMessages = messages
        .map((m, idx) => ({ msg: m, index: idx }))
        .filter(item => getMessageAuthor(item.msg) === author);

    const targetAuthorIndex = authorMessages.findIndex(item => item.index === targetIndex);

    // Mostrar mensajes anteriores del mismo autor
    console.log(`\n📤 MENSAJES ANTERIORES del mismo autor (${author}):`);
    const prevMessages = authorMessages.slice(Math.max(0, targetAuthorIndex - CONTEXT_MESSAGES), targetAuthorIndex);

    if (prevMessages.length === 0) {
        console.log('   (ninguno)');
    } else {
        for (const item of prevMessages) {
            const m = item.msg;
            const timeDiff = targetMsg.timestamp - m.timestamp;
            console.log(`\n   [${formatTimestamp(m.timestamp)}] (${timeDiff}s antes)`);
            console.log(`   Has Media: ${m.hasMedia ? 'SÍ' : 'NO'}`);
            console.log(`   Body: "${m.body || '(vacío)'}"`);
            if (m.body) {
                const codigo = extractCodigoCliente(m.body);
                console.log(`   Código extraído: ${codigo || '(ninguno)'}`);
            }
        }
    }

    // Mostrar mensajes posteriores del mismo autor
    console.log(`\n📥 MENSAJES POSTERIORES del mismo autor (${author}):`);
    const nextMessages = authorMessages.slice(targetAuthorIndex + 1, targetAuthorIndex + 1 + CONTEXT_MESSAGES);

    if (nextMessages.length === 0) {
        console.log('   (ninguno)');
    } else {
        for (const item of nextMessages) {
            const m = item.msg;
            const timeDiff = m.timestamp - targetMsg.timestamp;
            console.log(`\n   [${formatTimestamp(m.timestamp)}] (${timeDiff}s después)`);
            console.log(`   Has Media: ${m.hasMedia ? 'SÍ' : 'NO'}`);
            console.log(`   Body: "${m.body || '(vacío)'}"`);
            if (m.body) {
                const codigo = extractCodigoCliente(m.body);
                console.log(`   Código extraído: ${codigo || '(ninguno)'}`);
            }

            // Marcar si este mensaje cumple las condiciones
            if (!m.hasMedia && m.body && timeDiff <= 60) {
                const codigo = extractCodigoCliente(m.body);
                if (codigo) {
                    console.log(`   ✅ ESTE MENSAJE DEBERÍA HABER PROPORCIONADO EL CÓDIGO: ${codigo}`);
                }
            }
        }
    }

    // Análisis de por qué quedó como DESCONOCIDO
    console.log('\n' + '='.repeat(80));
    console.log('🔍 ANÁLISIS:');

    const codigoEnBody = extractCodigoCliente(targetMsg.body);
    if (codigoEnBody) {
        console.log(`   ⚠️  El mensaje tenía código en body (${codigoEnBody}), no debería ser DESCONOCIDO`);
        return true;
    }

    if (nextMessages.length === 0) {
        console.log('   ❌ No hay mensajes posteriores del mismo autor');
        return true;
    }

    const nextMsg = nextMessages[0].msg;
    const timeDiff = nextMsg.timestamp - targetMsg.timestamp;

    if (nextMsg.hasMedia) {
        console.log('   ❌ El siguiente mensaje es una imagen, no texto');
    } else if (!nextMsg.body) {
        console.log('   ❌ El siguiente mensaje no tiene texto');
    } else if (timeDiff > 60) {
        console.log(`   ❌ El siguiente mensaje está muy lejos (${timeDiff}s > 60s)`);
    } else {
        const codigo = extractCodigoCliente(nextMsg.body);
        if (!codigo) {
            console.log(`   ❌ El siguiente mensaje no contiene números: "${nextMsg.body}"`);
        } else {
            console.log(`   ⚠️  Hay un código disponible (${codigo}) pero quedó como DESCONOCIDO`);
            console.log('   Posible bug o el mensaje fue procesado antes de que llegara el código');
        }
    }

    return true;
}

async function main() {
    const args = process.argv.slice(2);

    if (args.length === 0) {
        console.log('Uso:');
        console.log('  node tests/search_whatsapp_context.js <message_id>');
        console.log('  node tests/search_whatsapp_context.js --list-desconocidos');
        console.log('  node tests/search_whatsapp_context.js --analyze-all');
        process.exit(0);
    }

    const mode = args[0];

    client.on('qr', (qr) => {
        qrcode.generate(qr, { small: true });
        console.log('ESCANEA ESTE CODIGO QR CON TU WHATSAPP');
    });

    client.on('ready', async () => {
        console.log('Cliente listo.\n');

        try {
            const chats = await client.getChats();
            const chat = chats.find(c => c.isGroup && c.name === TARGET_GROUP_NAME);

            if (!chat) {
                console.log(`❌ No se encontró el grupo "${TARGET_GROUP_NAME}"`);
                process.exit(1);
            }

            console.log(`Cargando mensajes de "${chat.name}"...`);
            const messages = await chat.fetchMessages({ limit: HISTORY_LIMIT });
            messages.sort((a, b) => a.timestamp - b.timestamp);
            console.log(`${messages.length} mensajes cargados.\n`);

            if (mode === '--list-desconocidos') {
                const desconocidos = await getDesconocidosFromDB();
                console.log(`\nComprobantes DESCONOCIDO en BD: ${desconocidos.length}\n`);
                for (const d of desconocidos) {
                    console.log(`  ${d.message_id}`);
                    console.log(`    Author: ${d.author || '(no registrado)'}`);
                    console.log(`    Imagen: ${d.imagen_path || '(sin imagen)'}\n`);
                }
            } else if (mode === '--analyze-all') {
                const desconocidos = await getDesconocidosFromDB();
                console.log(`\nAnalizando ${desconocidos.length} comprobantes DESCONOCIDO...\n`);

                for (const d of desconocidos) {
                    console.log('\n' + '='.repeat(80));
                    await searchMessageContext(messages, d.message_id);
                }
            } else {
                // Buscar un message_id específico
                await searchMessageContext(messages, mode);
            }

        } catch (error) {
            console.error('Error:', error.message);
        }

        await pool.end();
        process.exit(0);
    });

    client.initialize();
}

main();
