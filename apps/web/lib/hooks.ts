'use client';
import {useCallback,useEffect,useState} from 'react';
import {api,ApiError} from './api';
export function useResource<T>(path:string){
 const [data,setData]=useState<T|null>(null);const [error,setError]=useState('');const [loading,setLoading]=useState(true);
 const refresh=useCallback(async()=>{setError('');try{const result=await api<T>(path);setData(result);}catch(e){if(e instanceof ApiError&&e.status===401){window.location.assign('/login');return;}setError(e instanceof Error?e.message:'Unable to load data');}finally{setLoading(false);}},[path]);
 useEffect(()=>{setLoading(true);setData(null);void refresh();},[refresh]);
 return {data,error,loading,refresh};
}
