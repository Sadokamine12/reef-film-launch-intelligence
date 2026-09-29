'use client';
import {useEffect,useRef,useState} from 'react';
import 'leaflet/dist/leaflet.css';
export default function GeoMap({lat=48.259828,lon=11.670136,small=false,zone='all'}:{lat?:number;lon?:number;small?:boolean;zone?:string}){
 const el=useRef<HTMLDivElement>(null);const [error,setError]=useState(false);
 useEffect(()=>{let disposed=false;let cleanup:(()=>void)|undefined;
  import('leaflet').then(L=>{if(disposed||!el.current)return;const map=L.map(el.current,{scrollWheelZoom:false,zoomControl:!small,attributionControl:true}).setView([lat,lon],small?8:9);
   const layer=L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',maxZoom:18}).addTo(map);
   layer.on('tileerror',()=>setError(true));
   for(const [id,radius,color] of [['zone-c',50000,'#68c8d5'],['zone-b',30000,'#27a2ad'],['zone-a',15000,'#007b81']] as const){if(zone==='all'||zone===id)L.circle([lat,lon],{radius,color,fillColor:color,fillOpacity:.10,weight:1.5}).addTo(map).bindTooltip(`${id.replace('zone-','Zone ').toUpperCase()} · ${radius/1000} km`);}
   L.circleMarker([lat,lon],{radius:6,color:'white',weight:2,fillColor:'#102b42',fillOpacity:1}).addTo(map).bindTooltip('ESO Supernova',{permanent:true,direction:'bottom',offset:[0,7]});
   cleanup=()=>map.remove();
  }).catch(()=>setError(true));
  return()=>{disposed=true;cleanup?.();};
 },[lat,lon,small,zone]);
 return <div className={small?'mini-map':'map'}><div ref={el} style={{height:'100%',width:'100%'}} aria-label="Map centered on ESO Supernova with 15, 30 and 50 kilometre advertising zones"/>{error&&<div className="map-error">Map tiles are unavailable. Zone radii remain shown around ESO.</div>}</div>;
}
