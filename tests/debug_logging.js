/**
 * Script de Logging Detallado para Diagnóstico
 *
 * Este script es una versión modificada del bot que agrega logging extensivo
 * para entender por qué los mensajes quedan como DESCONOCIDO.
 *
 * Uso: node tests/debug_logging.js
 *
 * Los logs mostrarán:
 * - Por qué un comprobante quedó sin código
 * - El siguiente mensaje del autor (si existe)
 * - La diferencia de tiempo entre mensajes
 * - Si el siguiente mensaje tiene media o no
 */

const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const path = require('path');

// Configuración
const HISTORY_LIMIT = 50; // Limitar para debug
const TARGET_GROUP_NAME = 'Transferencias Badie';
const HISTORICAL_MAX_TIME_DIFF = 60; // 1 minuto en segundos

const client = new Client({
    authStrategy: new LocalAuth(),
    puppeteer: {
        headless: true,
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    }
});

function extractCodigoCliente(text) {
    if (!text || typeof text !== 'string') return null;
    const matches = text.match(/\d+/g);
    if (matches && matches.length > 0) {
        return matches[0];
    }
    return null;
}

function getMessageAuthor(msg) {
    return msg.author || msg.from;
}

function formatTimestamp(timestamp) {
    return new Date(timestamp * 1000).toLocaleString('es-AR');
}

async function analyzeMessages() {
    console.log('='.repeat(80));
    console.log('ANÁLISIS DE MENSAJES - DEBUG LOGGING');
    console.log('='.repeat(80));

    const chats = await client.getChats();

    for (const chat of chats) {
        if (!chat.isGroup || chat.name !== TARGET_GROUP_NAME) {
            continue;
        }

        console.log(`\nAnalizando chat: ${chat.name}`);
        console.log('-'.repeat(80));

        const messages = await chat.fetchMessages({ limit: HISTORY_LIMIT });
        messages.sort((a, b) => a.timestamp - b.timestamp);

        const mediaMessages = messages.filter(m => m.hasMedia);
        console.log(`Total mensajes: ${messages.length}`);
        console.log(`Mensajes con media: ${mediaMessages.length}`);
        console.log('-'.repeat(80));

        let desconocidoCount = 0;
        let conCodigoCount = 0;

        for (let i = 0; i < messages.length; i++) {
            const msg = messages[i];

            if (!msg.hasMedia) continue;

            const author = getMessageAuthor(msg);
            const codigoEnBody = extractCodigoCliente(msg.body);

            console.log(`\n[${'#'.repeat(3)} COMPROBANTE ${i} ${'#'.repeat(50)}`);
            console.log(`  Message ID: ${msg.id._serialized}`);
            console.log(`  Author: ${author}`);
            console.log(`  Timestamp: ${formatTimestamp(msg.timestamp)}`);
            console.log(`  Body: "${msg.body || '(vacío)'}"`);

            if (codigoEnBody) {
                console.log(`  ✅ CÓDIGO EN BODY: ${codigoEnBody}`);
                conCodigoCount++;
                continue;
            }

            console.log(`  ⚠️  Sin código en body, buscando siguiente mensaje...`);

            // Buscar siguiente mensaje del mismo autor
            let nextMessage = null;
            let nextIndex = -1;

            for (let j = i + 1; j < messages.length; j++) {
                const candidate = messages[j];
                if (getMessageAuthor(candidate) === author) {
                    nextIndex = j;
                    nextMessage = candidate;
                    break;
                }
            }

            if (!nextMessage) {
                console.log(`  ❌ RESULTADO: DESCONOCIDO`);
                console.log(`     Razón: No hay siguiente mensaje del mismo autor`);
                desconocidoCount++;
                continue;
            }

            const timeDiff = nextMessage.timestamp - msg.timestamp;

            console.log(`\n  Siguiente mensaje encontrado (índice ${nextIndex}):`);
            console.log(`    Timestamp: ${formatTimestamp(nextMessage.timestamp)}`);
            console.log(`    Diferencia: ${timeDiff} segundos`);
            console.log(`    Tiene media: ${nextMessage.hasMedia ? 'SÍ' : 'NO'}`);
            console.log(`    Body: "${nextMessage.body || '(vacío)'}"`);

            // Verificar condiciones
            if (nextMessage.hasMedia) {
                console.log(`  ❌ RESULTADO: DESCONOCIDO`);
                console.log(`     Razón: Siguiente mensaje es una imagen, no texto`);
                desconocidoCount++;
                continue;
            }

            if (!nextMessage.body) {
                console.log(`  ❌ RESULTADO: DESCONOCIDO`);
                console.log(`     Razón: Siguiente mensaje no tiene texto`);
                desconocidoCount++;
                continue;
            }

            if (timeDiff > HISTORICAL_MAX_TIME_DIFF) {
                console.log(`  ❌ RESULTADO: DESCONOCIDO`);
                console.log(`     Razón: Siguiente mensaje está fuera del tiempo límite (${timeDiff}s > ${HISTORICAL_MAX_TIME_DIFF}s)`);
                desconocidoCount++;
                continue;
            }

            const codigoNext = extractCodigoCliente(nextMessage.body);

            if (!codigoNext) {
                console.log(`  ❌ RESULTADO: DESCONOCIDO`);
                console.log(`     Razón: Siguiente mensaje no contiene código numérico`);
                desconocidoCount++;
                continue;
            }

            console.log(`  ✅ CÓDIGO ENCONTRADO: ${codigoNext}`);
            conCodigoCount++;
        }

        console.log('\n' + '='.repeat(80));
        console.log('RESUMEN:');
        console.log(`  Con código: ${conCodigoCount}`);
        console.log(`  DESCONOCIDO: ${desconocidoCount}`);
        console.log('='.repeat(80));
    }

    process.exit(0);
}

client.on('qr', (qr) => {
    qrcode.generate(qr, { small: true });
    console.log('ESCANEA ESTE CODIGO QR CON TU WHATSAPP');
});

client.on('ready', async () => {
    console.log('Cliente listo. Iniciando análisis...\n');
    await analyzeMessages();
});

client.initialize();
