import { NextRequest } from 'next/server';
export const dynamic = 'force-dynamic';
const methods = new Set(['GET','POST','PUT','PATCH']);
async function proxy(request: NextRequest, context: {params: Promise<{path:string[]}>}) {
  const {path} = await context.params;
  if (!methods.has(request.method) || path.some(p => !/^[a-zA-Z0-9_.-]+$/.test(p)) || !['v1','health'].includes(path[0]))
    return Response.json({detail:'Route not available'},{status:404});
  if (request.method !== 'GET') {
    const origin = request.headers.get('origin');
    const expected = process.env.APP_ORIGIN || request.nextUrl.origin;
    if (origin !== expected) return Response.json({detail:'Origin not allowed'},{status:403});
  }
  const size = Number(request.headers.get('content-length') || '0');
  if (size > 2100000) return Response.json({detail:'File exceeds 2 MB'},{status:413});
  const base = process.env.API_BASE_URL;
  if (!base) return Response.json({detail:'API connection is not configured'},{status:503});
  const headers = new Headers();
  for (const key of ['content-type','cookie','origin']) {
    const value=request.headers.get(key); if(value) headers.set(key,value);
  }
  try {
    const body=request.method==='GET'?undefined:await request.arrayBuffer();
    if (body && body.byteLength > 2100000) return Response.json({detail:'File exceeds 2 MB'},{status:413});
    const res = await fetch(`${base.replace(/\/$/,'')}/${path.join('/')}${request.nextUrl.search}`,{
      method:request.method,headers,body,cache:'no-store',signal:AbortSignal.timeout(20000),redirect:'error'
    });
    const out=new Headers({'Cache-Control':'no-store'});
    for(const key of ['content-type','content-disposition','x-request-id']) {const v=res.headers.get(key);if(v)out.set(key,v);}
    for(const cookie of res.headers.getSetCookie()) out.append('set-cookie',cookie);
    return new Response(res.body,{status:res.status,headers:out});
  } catch {return Response.json({detail:'The REEF API is unavailable. Your data has not been changed.'},{status:503});}
}
export {proxy as GET, proxy as POST, proxy as PUT, proxy as PATCH};
