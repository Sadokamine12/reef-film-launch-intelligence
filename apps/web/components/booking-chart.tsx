'use client';
import {ResponsiveContainer,ComposedChart,Line,Area,XAxis,YAxis,CartesianGrid,Tooltip,ReferenceLine} from 'recharts';
import type {CurvePoint,Historical,SalesTrajectoryPoint} from '@reef/types';
export function BookingChart({curve,actual=[],history=[],forecast=[],capacity=109}:{curve:CurvePoint[];actual?:CurvePoint[];history?:Historical[];forecast?:SalesTrajectoryPoint[];capacity?:number}){
 const days=new Set([...curve.map(p=>p.days),...actual.map(p=>p.days),...forecast.map(p=>p.days)]);
 const rows=[...days].sort((a,b)=>b-a).map(days=>({
  days,
  target:curve.find(p=>p.days===days)?.tickets,
  actual:actual.filter(p=>p.days===days).at(-1)?.tickets,
  forecastLow:forecast.find(p=>p.days===days)?.low,
  forecastBase:forecast.find(p=>p.days===days)?.base,
  forecastHigh:forecast.find(p=>p.days===days)?.high,
 }));
 return <div className="chart" role="img" aria-label="Booking curve with management target, observations and model forecast"><ResponsiveContainer width="100%" height="100%"><ComposedChart margin={{top:12,right:15,left:-20,bottom:8}} data={rows}><CartesianGrid stroke="#eaf0f3" vertical={false}/><XAxis dataKey="days" type="number" domain={[0,'dataMax']} reversed tick={{fill:'#778b99',fontSize:11}} axisLine={false} tickLine={false} tickFormatter={v=>v===0?'Show':`${v}d`}/><YAxis domain={[0,capacity]} tick={{fill:'#778b99',fontSize:11}} axisLine={false} tickLine={false}/><Tooltip labelFormatter={v=>`${v} days before screening`} contentStyle={{border:'1px solid #dde8ec',borderRadius:8,fontSize:12}}/><Area name="Management target" type="linear" dataKey="target" stroke="#008e94" fill="#dcf2f0" strokeWidth={2.5} dot={{r:3,fill:'#008e94',strokeWidth:0}} connectNulls/><Line name="Forecast low" dataKey="forecastLow" type="linear" stroke="#81a2b5" strokeWidth={1.2} strokeDasharray="3 4" dot={false} connectNulls/><Line name="Forecast high" dataKey="forecastHigh" type="linear" stroke="#81a2b5" strokeWidth={1.2} strokeDasharray="3 4" dot={false} connectNulls/><Line name="Forecast base" dataKey="forecastBase" type="linear" stroke="#6d5cae" strokeWidth={2.5} strokeDasharray="6 4" dot={{r:3,fill:'#6d5cae'}} connectNulls/><Line name="Observed tickets" dataKey="actual" type="linear" stroke="#173957" strokeWidth={2.5} dot={{r:4,fill:'#173957'}} connectNulls/>{history.length>0&&<Line name="Historical inventory" data={history.map(p=>({days:p.days_before,inventory:p.unavailable_seats})).sort((a,b)=>b.days-a.days)} dataKey="inventory" stroke="#d49a45" strokeWidth={1.5} strokeDasharray="4 4" dot={{r:3}}/>}<ReferenceLine y={capacity} stroke="#d4dee4" strokeDasharray="3 3"/></ComposedChart></ResponsiveContainer></div>;
}
