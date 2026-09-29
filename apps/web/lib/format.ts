export const money=(cents:number|null|undefined)=>cents==null?'—':new Intl.NumberFormat('en-IE',{style:'currency',currency:'EUR',maximumFractionDigits:cents%100?2:0}).format(cents/100);
export const number=(value:number|null|undefined)=>value==null?'—':new Intl.NumberFormat('en-GB',{maximumFractionDigits:2}).format(value);
export const shortDate=(value:string)=>new Intl.DateTimeFormat('en-GB',{day:'2-digit',month:'short',timeZone:'Europe/Berlin'}).format(new Date(value.length===10?value+'T12:00:00Z':value));
export const weekday=(value:string)=>new Intl.DateTimeFormat('en-GB',{weekday:'short',timeZone:'Europe/Berlin'}).format(new Date(value.length===10?value+'T12:00:00Z':value));
export const fullDate=(value:string)=>new Intl.DateTimeFormat('en-GB',{day:'numeric',month:'long',year:'numeric',timeZone:'Europe/Berlin'}).format(new Date(value.length===10?value+'T12:00:00Z':value));
export const percent=(value:number|null|undefined)=>value==null?'—':`${number(value)}%`;
