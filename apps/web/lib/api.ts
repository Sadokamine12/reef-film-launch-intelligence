export class ApiError extends Error {constructor(message:string,public status:number){super(message);}}
export async function api<T>(path:string,options:RequestInit={}):Promise<T>{
  const headers=new Headers(options.headers);
  if(options.body && !(options.body instanceof FormData))headers.set('Content-Type','application/json');
  const response=await fetch(`/api/v1${path}`,{...options,headers,credentials:'same-origin',cache:'no-store'});
  if(!response.ok){
    let message='The request could not be completed.';
    try{const body=await response.json(); message=typeof body.detail==='string'?body.detail:JSON.stringify(body.detail);}catch{}
    throw new ApiError(message,response.status);
  }
  return response.json();
}
