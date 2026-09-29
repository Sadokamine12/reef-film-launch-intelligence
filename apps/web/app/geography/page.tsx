'use client';
import dynamic from 'next/dynamic';
import {useState} from 'react';
import {Info,MapPin} from 'lucide-react';
import {Select} from '@reef/ui';
import type {Dashboard,Geography} from '@reef/types';
import {useResource} from '@/lib/hooks';
import {money,number} from '@/lib/format';
import {PageTitle,Panel,Loading,ErrorState,SourceBadge} from '@/components/shared';
const GeoMap=dynamic(()=>import('@/components/geo-map'),{ssr:false});
export default function GeographyPage(){
 const {data:d,error,loading,refresh}=useResource<Dashboard>('/dashboard');const geo=useResource<Geography[]>('/geography');const [zone,setZone]=useState('all');
 if(loading||geo.loading)return <Loading/>;if(error||geo.error||!d||!geo.data)return <ErrorState message={error||geo.error} retry={()=>{void refresh();void geo.refresh();}}/>;
 return <><PageTitle eyebrow="GEOGRAPHIC INTELLIGENCE" title="Start close. Expand with evidence." description="Three advertising zones around ESO Supernova in Garching."/><div className="toolbar"><div className="inline-actions"><MapPin size={18}/><span className="microcopy">Karl-Schwarzschild-Straße 2 · Garching bei München</span></div><Select aria-label="Advertising zone" value={zone} onChange={e=>setZone(e.target.value)}><option value="all">All advertising zones</option>{geo.data.map(z=><option key={z.id} value={z.id}>{z.name}</option>)}</Select></div>
 <div className="split-layout"><Panel title="ESO advertising catchment" aside={<SourceBadge source="PLANNING ASSUMPTION"/>}><GeoMap lat={d.project.latitude} lon={d.project.longitude} zone={zone}/><p className="microcopy section-gap">Radii show straight-line distance from the venue. Actual travel time and platform targeting boundaries differ. Select the matching zone when creating each ad set.</p></Panel><div>{geo.data.map((g,i)=><section className="card zone-card" key={g.id} style={{borderLeftColor:['#007f80','#34abb4','#81c8d4'][i]}}><h3>{g.name}<span className="microcopy">{g.min_km}–{g.max_km} km</span></h3><SourceBadge source={g.priority}/><p>{g.notes}</p><div className="zone-metrics"><div><small>Recorded spend</small><strong>{money(g.performance.spend_cents)}</strong></div><div><small>Ticket signal</small><strong>{number(g.performance.attributed_tickets)}</strong></div><div><small>Cost / ticket</small><strong>{money(g.performance.cost_per_ticket_cents)}</strong></div></div></section>)}</div></div><div className="notice section-gap"><Info size={18}/><span>Zone priority is a planning assumption. Cost per ticket appears after campaign spend and explicit ticket attribution are imported. A ticket signal is attributed, not proven incremental.</span></div></>;
}
