'use client';
import {useState} from 'react';
import {Plus} from 'lucide-react';
import {Button,Dialog,DialogTrigger,DialogContent,DialogTitle,DialogDescription,Input,Label,Select,Textarea} from '@reef/ui';
import type {Screening} from '@reef/types';
import {api} from '@/lib/api';
import {shortDate} from '@/lib/format';
import {Feedback} from './shared';
import {useUser} from './shell';
export function SalesEntry({screenings,onSaved}:{screenings:Screening[];onSaved:()=>void}){
 const [open,setOpen]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState('');const user=useUser();
 return <Dialog open={open} onOpenChange={v=>{setOpen(v);setError('');}}><DialogTrigger asChild><Button disabled={user?.role==='viewer'}><Plus size={16}/>Record ticket sales</Button></DialogTrigger><DialogContent><DialogTitle>Record ticket sales</DialogTitle><DialogDescription className="dialog-description">Enter a confirmed cumulative ticket count from ESO. This observation will immediately update the sales plan.</DialogDescription><form onSubmit={async e=>{e.preventDefault();setBusy(true);setError('');const f=new FormData(e.currentTarget);try{await api('/ticket-sales',{method:'POST',body:JSON.stringify({screening_id:f.get('screening_id'),tickets_sold:Number(f.get('tickets_sold')),observed_at:new Date(String(f.get('observed_at'))).toISOString(),note:f.get('note')})});setOpen(false);onSaved();}catch(err){setError(err instanceof Error?err.message:'Could not save');}finally{setBusy(false);}}}>
 <div className="field"><Label htmlFor="sale-screening">Screening</Label><Select id="sale-screening" name="screening_id" required>{screenings.map(s=><option key={s.id} value={s.id}>{shortDate(s.date)} 2027 · {s.capacity} seats</option>)}</Select></div>
 <div className="form-grid"><div className="field"><Label htmlFor="ticket-count">Total tickets sold</Label><Input id="ticket-count" name="tickets_sold" type="number" min="0" max="109" required placeholder="e.g. 38"/></div><div className="field"><Label htmlFor="observed-at">Observed at (your local time)</Label><Input id="observed-at" name="observed_at" type="datetime-local" defaultValue={new Date(Date.now()-new Date().getTimezoneOffset()*60000).toISOString().slice(0,16)} required/></div></div>
 <div className="field"><Label htmlFor="sale-note">Source / note</Label><Textarea id="sale-note" name="note" placeholder="ESO sales report, contact or a refund explanation"/><p className="field-help">A lower count needs an explanation. Unavailable inventory may include held seats.</p></div><Feedback error={error}/><div className="form-actions"><Button variant="outline" type="button" onClick={()=>setOpen(false)}>Cancel</Button><Button disabled={busy} type="submit">{busy?'Saving…':'Save observation'}</Button></div></form></DialogContent></Dialog>;
}
