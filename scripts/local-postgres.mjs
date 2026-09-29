// Local development only. Production uses standard PostgreSQL; CI uses PostgreSQL 17.
import { mkdirSync } from 'node:fs';
import { dirname } from 'node:path';
import { PGlite } from '@electric-sql/pglite';
import { PGLiteSocketServer } from '@electric-sql/pglite-socket';
const dbPath = process.env.REEF_LOCAL_DB || '.local/postgres';
mkdirSync(dirname(dbPath), { recursive: true });
const db = await PGlite.create(dbPath);
const server = new PGLiteSocketServer({ db, host: '127.0.0.1', port: Number(process.env.PGPORT || 5432), path: process.env.REEF_PG_SOCKET });
await server.start();
console.log('Local PGlite PostgreSQL development database listening on 127.0.0.1:' + (process.env.PGPORT || 5432));
async function stop() { await server.stop(); await db.close(); process.exit(0); }
process.on('SIGTERM', stop);
process.on('SIGINT', stop);
