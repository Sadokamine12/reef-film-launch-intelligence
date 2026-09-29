'use client';
import Link from 'next/link';
import {ArrowRight,AlertCircle,RefreshCw,Inbox} from 'lucide-react';
import {Badge,Button,Card,CardContent,CardHeader,CardTitle} from '@reef/ui';
import type {SourceLabel,Status} from '@reef/types';
export function StatusBadge({status}:{status:Status|string}){return <Badge className={`status status-${status.toLowerCase()}`}>{status.replaceAll('_',' ')}</Badge>;}
export function SourceBadge({source}:{source:SourceLabel|string}){return <Badge className="source-badge">{source}</Badge>;}
export function PageTitle({eyebrow,title,description,action}:{eyebrow?:string;title:string;description?:string;action?:React.ReactNode}){return <div className="page-heading"><div>{eyebrow&&<div className="eyebrow">{eyebrow}</div>}<h1>{title}</h1>{description&&<p>{description}</p>}</div>{action}</div>;}
export function Panel({title,aside,children,className=''}:{title:string;aside?:React.ReactNode;children:React.ReactNode;className?:string}){return <Card className={className}><CardHeader><CardTitle>{title}</CardTitle>{aside}</CardHeader><CardContent>{children}</CardContent></Card>;}
export function Metric({label,value,detail,icon}:{label:string;value:React.ReactNode;detail:string;icon?:React.ReactNode}){return <Card className="metric"><div className="metric-top"><span>{label}</span>{icon}</div><strong>{value}</strong><p>{detail}</p></Card>;}
export function Loading(){return <div aria-label="Loading workspace" className="loading-grid">{[1,2,3,4,5,6].map(i=><div className="skeleton" key={i}/>)}</div>;}
export function ErrorState({message,retry}:{message:string;retry:()=>void}){return <div className="error-state" role="alert"><AlertCircle/><h2>We couldn’t load this view</h2><p>{message}</p><Button onClick={retry} variant="outline"><RefreshCw size={16}/>Try again</Button></div>;}
export function Empty({title,detail,action}:{title:string;detail:string;action?:React.ReactNode}){return <div className="empty"><Inbox size={30}/><h3>{title}</h3><p>{detail}</p>{action}</div>;}
export function TextLink({href,children}:{href:string;children:React.ReactNode}){return <Link className="text-link" href={href}>{children}<ArrowRight size={15}/></Link>;}
export function Feedback({error,success}:{error?:string;success?:string}){return error?<p className="form-error" role="alert">{error}</p>:success?<p className="form-success" role="status">{success}</p>:null;}
