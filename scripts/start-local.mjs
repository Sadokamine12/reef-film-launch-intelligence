// Local evaluation only. Binds all services to your own computer.
import {PGlite} from '@electric-sql/pglite';
import {PGLiteSocketServer} from '@electric-sql/pglite-socket';
import {spawn} from 'node:child_process';
import {mkdirSync,existsSync} from 'node:fs';
import path from 'node:path';
const root=path.resolve(import.meta.dirname,'..');
process.chdir(root);
const python=path.join(root,'.venv',process.platform==='win32'?'Scripts/python.exe':'bin/python');
if(!existsSync(python)||!existsSync('apps/web/.next/BUILD_ID')){
 console.error('Run SETUP_LOCAL first. Node.js 22+ and Python 3.12+ are required.');process.exit(1);
}
mkdirSync('.local',{recursive:true});
const db=await PGlite.create('.local/local-test-database');
const dbServer=new PGLiteSocketServer({db,host:'127.0.0.1',port:55432});
await dbServer.start();
const env={...process.env,ENVIRONMENT:'development',DEV_AUTH_BYPASS:'true',DB_POOL_SIZE:'1',DATABASE_URL:'postgresql+psycopg://postgres:postgres@127.0.0.1:55432/postgres',CORS_ORIGINS:'http://localhost:3000,http://127.0.0.1:3000',API_BASE_URL:'http://127.0.0.1:8000',APP_ORIGIN:'http://localhost:3000'};
const children=[];
function start(cmd,args){const child=spawn(cmd,args,{cwd:root,stdio:'inherit',env});children.push(child);return child;}
async function run(cmd,args){const child=start(cmd,args);const code=await new Promise((resolve,reject)=>{child.once('error',reject);child.once('exit',resolve);});if(code!==0)throw new Error(`${cmd} failed (${code})`);}
async function wait(url){for(let i=0;i<60;i++){try{if((await fetch(url)).ok)return;}catch{}await new Promise(r=>setTimeout(r,500));}throw new Error(`Service did not start: ${url}`);}
let stopping=false;
async function stop(code=0){if(stopping)return;stopping=true;for(const c of children)if(c.exitCode===null)c.kill();await dbServer.stop();await db.close();process.exit(code);}
process.on('SIGINT',()=>stop());process.on('SIGTERM',()=>stop());
try{
 await run(python,['-m','alembic','-c','apps/api/alembic.ini','upgrade','head']);
 await run(python,['-m','reef.seed']);
 start(python,['-m','uvicorn','reef.main:app','--host','127.0.0.1','--port','8000']);
 await wait('http://127.0.0.1:8000/health/ready');
 start(process.execPath,['node_modules/next/dist/bin/next','start','apps/web','--hostname','127.0.0.1','--port','3000']);
 await wait('http://127.0.0.1:3000/login');
 console.log('\nREEF Launch Intelligence is ready: http://localhost:3000\nLocal testing mode: no login required. Data persists in .local/local-test-database.\nKeep this window open. Press Ctrl+C to stop.\n');
}catch(error){console.error(error.message);await stop(1);}
