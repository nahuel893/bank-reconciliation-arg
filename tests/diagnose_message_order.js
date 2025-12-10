/**
 * Script de diagnóstico para analizar el orden de mensajes en WhatsApp
 *
 * Uso: node tests/diagnose_message_order.js
 *
 * Este script muestra los mensajes en el orden que los recibe y después de ordenar,
 * para identificar discrepancias entre el orden visual en WhatsApp y el orden por timestamp.
 */

const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');

const HISTORY_LIMIT = 50; // Últimos 50 mensajes para diagnóstico
const TARGET_GROUP_NAME = 'Transferencias Badie';

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

function formatTimestamp(ts) {
    return new Date(ts * 1000).toLocaleString('es-AR');
}

client.on('qr', (qr) => {
    qrcode.generate(qr, { small: true });
    console.log('ESCANEA ESTE CODIGO QR CON TU WHATSAPP');
});

client.on('ready', async () => {
    console.log('Cliente listo. Analizando mensajes...\n');

    const chats = await client.getChats();
    const targetChat = chats.find(c => c.isGroup && c.name === TARGET_GROUP_NAME);

    if (!targetChat) {
        console.log(`No se encontró el grupo "${TARGET_GROUP_NAME}"`);
        process.exit(1);
    }

    const messages = await targetChat.fetchMessages({ limit: HISTORY_LIMIT });

    console.log('='.repeat(80));
    console.log('ORDEN ORIGINAL (como llega de WhatsApp API)');
    console.log('='.repeat(80));

    messages.forEach((msg, idx) => {
        const author = getMessageAuthor(msg);
        const authorShort = author ? author.split('@')[0].slice(-4) : '????';
        const type = msg.hasMedia ? '📷 IMAGEN' : '📝 TEXTO';
        const body = msg.body ? msg.body.substring(0, 30) : '(sin texto)';

        console.log(`[${idx.toString().padStart(2)}] ts:${msg.timestamp} | ${formatTimestamp(msg.timestamp)} | ${authorShort} | ${type} | ${body}`);
    });

    console.log('\n' + '='.repeat(80));
    console.log('ORDEN DESPUÉS DE SORT POR TIMESTAMP');
    console.log('='.repeat(80));

    const sorted = [...messages].sort((a, b) => a.timestamp - b.timestamp);

    sorted.forEach((msg, idx) => {
        const author = getMessageAuthor(msg);
        const authorShort = author ? author.split('@')[0].slice(-4) : '????';
        const type = msg.hasMedia ? '📷 IMAGEN' : '📝 TEXTO';
        const body = msg.body ? msg.body.substring(0, 30) : '(sin texto)';

        // Buscar posición original
        const originalIdx = messages.findIndex(m => m.id._serialized === msg.id._serialized);
        const moved = originalIdx !== idx ? ` (era ${originalIdx})` : '';

        console.log(`[${idx.toString().padStart(2)}] ts:${msg.timestamp} | ${formatTimestamp(msg.timestamp)} | ${authorShort} | ${type} | ${body}${moved}`);
    });

    // Buscar casos problemáticos: imagen seguida de texto de otro autor antes del texto correcto
    console.log('\n' + '='.repeat(80));
    console.log('ANÁLISIS DE POSIBLES PROBLEMAS');
    console.log('='.repeat(80));

    for (let i = 0; i < sorted.length; i++) {
        const msg = sorted[i];
        if (!msg.hasMedia) continue;

        const author = getMessageAuthor(msg);

        // Buscar siguiente mensaje del mismo autor
        let nextSameAuthor = null;
        let nextSameAuthorIdx = -1;

        for (let j = i + 1; j < sorted.length; j++) {
            if (getMessageAuthor(sorted[j]) === author) {
                nextSameAuthor = sorted[j];
                nextSameAuthorIdx = j;
                break;
            }
        }

        if (nextSameAuthor) {
            const timeDiff = nextSameAuthor.timestamp - msg.timestamp;
            const msgsBetween = nextSameAuthorIdx - i - 1;

            if (nextSameAuthor.hasMedia) {
                console.log(`\n⚠️  IMAGEN[${i}] -> IMAGEN[${nextSameAuthorIdx}] (sin texto entre ellas del mismo autor)`);
                console.log(`    Autor: ${author.split('@')[0]}`);
                console.log(`    Diff: ${timeDiff}s, Mensajes entre: ${msgsBetween}`);
            } else if (timeDiff > 60) {
                console.log(`\n⚠️  IMAGEN[${i}] -> TEXTO[${nextSameAuthorIdx}] (timeDiff > 60s: ${timeDiff}s)`);
                console.log(`    Autor: ${author.split('@')[0]}`);
                console.log(`    Texto: ${nextSameAuthor.body?.substring(0, 50)}`);
            }
        }
    }

    console.log('\n\nDiagnóstico completado.');
    process.exit(0);
});

client.initialize();
