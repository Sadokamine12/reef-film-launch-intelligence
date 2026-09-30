'use client';
import {useEffect,useState} from 'react';
import {Activity,Calculator,Euro,Info,Target,Wallet} from 'lucide-react';
import {CartesianGrid,Line,LineChart,ReferenceLine,ResponsiveContainer,Tooltip,XAxis,YAxis} from 'recharts';
import {Button,Input,Label,Table} from '@reef/ui';
import type {Dashboard,ScenarioResult,SourceLabel} from '@reef/types';
import {api} from '@/lib/api';
import {money,number,percent,shortDate,weekday} from '@/lib/format';
import {ErrorState,Feedback,Loading,Metric,PageTitle,Panel,SourceBadge} from '@/components/shared';
import {useResource} from '@/lib/hooks';

export default function ScenariosPage(){
 const {data,error,loading}=useResource<Dashboard>('/dashboard');
 if(loading)return <Loading/>;
 if(error||!data)return <ErrorState message={error} retry={()=>window.location.reload()}/>;
 return <ScenarioWorkspace dashboard={data}/>;
}

function ScenarioWorkspace({dashboard:d}:{dashboard:Dashboard}){
 const [selected,setSelected]=useState<string[]>(d.screenings.map(s=>s.id));
 const [price,setPrice]=useState((d.rules.baseline_ticket_price_cents/100).toFixed(2));
 const [budget,setBudget]=useState('0');
 const [target,setTarget]=useState(String(d.rules.attendance_target_pct));
 const [elasticity,setElasticity]=useState(String(d.rules.price_elasticity));
 const [cpa,setCpa]=useState(d.rules.ad_incremental_cpa_cents==null?'':String(d.rules.ad_incremental_cpa_cents/100));
 const [share,setShare]=useState(d.rules.revenue_share_bps==null?'':String(d.rules.revenue_share_bps/100));
 const [fixed,setFixed]=useState(d.rules.fixed_cost_cents==null?'':String(d.rules.fixed_cost_cents/100));
 const [variable,setVariable]=useState(d.rules.variable_cost_per_ticket_cents==null?'':String(d.rules.variable_cost_per_ticket_cents/100));
 const [cannibalization,setCannibalization]=useState(d.rules.cannibalization_pct==null?'':String(d.rules.cannibalization_pct));
 const [result,setResult]=useState<ScenarioResult|null>(null);
 const [busy,setBusy]=useState(false);
 const [error,setError]=useState('');

 const run=async()=>{
  setBusy(true);setError('');
  const optionalMoney=(value:string)=>value.trim()===''?undefined:Math.round(Number(value)*100);
  const optionalNumber=(value:string)=>value.trim()===''?undefined:Number(value);
  try{
   const payload={
    screening_ids:selected,
    ticket_price_cents:Math.round(Number(price)*100),
    advertising_budget_cents:Math.round(Number(budget)*100),
    attendance_target_pct:Number(target),
    price_elasticity:Number(elasticity),
    ad_incremental_cpa_cents:optionalMoney(cpa),
    revenue_share_bps:share.trim()===''?undefined:Math.round(Number(share)*100),
    fixed_cost_cents:optionalMoney(fixed),
    variable_cost_per_ticket_cents:optionalMoney(variable),
    cannibalization_pct:optionalNumber(cannibalization),
   };
   setResult(await api<ScenarioResult>('/scenarios',{method:'POST',body:JSON.stringify(payload)}));
  }catch(err){setError(err instanceof Error?err.message:'Unable to calculate scenario');}
  finally{setBusy(false);}
 };
 useEffect(()=>{void run();},[]); // initial scenario uses persisted defaults

 const toggle=(id:string)=>setSelected(current=>current.includes(id)?current.filter(x=>x!==id):[...current,id]);
 const p=result?.portfolio;
 return <>
  <PageTitle eyebrow="FORECAST & SCENARIOS" title="Resolution decision lab" description="Test ticket price, advertising budget and economics without confusing assumptions with observed evidence." action={<Button onClick={run} disabled={busy||selected.length===0}><Calculator size={17}/>{busy?'Calculating…':'Run scenario'}</Button>}/>
  <div className="scenario-layout">
   <Panel title="Scenario controls" aside={<SourceBadge source="USER INPUT"/>}>
    <div className="scenario-screening-picker">
     <div className="tiny-label">SCREENINGS</div>
     <div className="scenario-checks">{d.screenings.map(s=><label key={s.id}><input type="checkbox" checked={selected.includes(s.id)} onChange={()=>toggle(s.id)}/><span>{weekday(s.date)} {shortDate(s.date)}</span></label>)}</div>
    </div>
    <div className="form-grid scenario-fields">
     <Field label="Ticket price (€)" value={price} set={setPrice} min="0.01" step="0.50"/>
     <Field label="Advertising budget (€)" value={budget} set={setBudget} min="0" step="10"/>
     <Field label="Target occupancy (%)" value={target} set={setTarget} min="0" max="100" step="1"/>
     <Field label="Price elasticity" value={elasticity} set={setElasticity} min="-5" max="-0.01" step="0.1"/>
     <Field label="Planning incremental CPA (€)" value={cpa} set={setCpa} min="0.01" step="0.50" placeholder="Unknown"/>
     <Field label="REEF revenue share (%)" value={share} set={setShare} min="0" max="100" step="0.1" placeholder="Unknown"/>
     <Field label="REEF fixed costs (€)" value={fixed} set={setFixed} min="0" step="1" placeholder="Unknown"/>
     <Field label="Variable cost / ticket (€)" value={variable} set={setVariable} min="0" step="0.10" placeholder="Unknown"/>
     <Field label="Cannibalization (%)" value={cannibalization} set={setCannibalization} min="0" max="100" step="1" placeholder="Not estimated"/>
    </div>
    <p className="microcopy scenario-help"><Info size={15}/>Price elasticity, planning CPA and cannibalization are scenario assumptions until REEF collects evidence that can estimate them.</p>
    <Feedback error={error}/>
   </Panel>
   <Panel title="Evidence status" aside={<Activity size={18}/>}>
    <EvidenceRow label="Baseline demand" source={result?.evidence.baseline_demand.classification}/>
    <EvidenceRow label="Ticket price" source={result?.evidence.ticket_price.classification}/>
    <EvidenceRow label="Price response" source={result?.evidence.price_response.classification}/>
    <EvidenceRow label="Advertising response" source={result?.evidence.advertising_response.classification}/>
    <EvidenceRow label="REEF economics" source={result?.evidence.economics.classification}/>
    <EvidenceRow label="Cross-screening cannibalization" source={result?.evidence.cannibalization.classification}/>
    <div className="scenario-evidence-note"><strong>Based on what?</strong><p>Baseline demand comes from the grouped historical ESO model and any current Resolution observations. Price response and advertising lift remain explicit assumptions unless the evidence status says otherwise.</p></div>
   </Panel>
  </div>

  {result&&p&&<>
   <div className="kpi-grid section-gap">
    <Metric label="Expected tickets" value={number(p.tickets_base)} detail={`${number(p.tickets_low)}–${number(p.tickets_high)} planning range`} icon={<Target/>}/>
    <Metric label="Expected occupancy" value={percent(p.occupancy_base_pct)} detail={`${p.capacity} seats across ${result.screenings.length} selected shows`} icon={<Activity/>}/>
    <Metric label="Gross ticket revenue" value={money(p.gross_revenue_base_cents)} detail={`${money(p.gross_revenue_low_cents)}–${money(p.gross_revenue_high_cents)} range`} icon={<Euro/>}/>
    <Metric label={p.economics_complete?'Provisional REEF contribution':'REEF contribution'} value={money(p.provisional_contribution_cents)} detail={p.economics_complete?'Uses entered share and costs':'Enter revenue share + fixed + variable costs'} icon={<Wallet/>}/>
   </div>

   <div className="two-columns section-gap">
    <Panel title="Ticket price → expected demand" aside={<SourceBadge source="PLANNING ASSUMPTION"/>}><ScenarioChart data={result.price_ladder.map(r=>({x:r.ticket_price_cents/100,tickets:r.tickets_base,revenue:r.gross_revenue_base_cents/100}))} target={p.capacity*result.attendance_target_pct/100}/><div className="scenario-insights"><div><span>Highest tested price meeting target</span><strong>{money(result.highest_tested_price_meeting_target_cents)}</strong></div><div><span>Revenue-maximizing tested price</span><strong>{money(result.revenue_maximizing_tested_price_cents)}</strong></div></div></Panel>
    <Panel title="Advertising budget → expected demand" aside={<SourceBadge source={result.evidence.advertising_response.classification}/>}><BudgetChart data={result.budget_ladder.map(r=>({x:r.advertising_budget_cents/100,tickets:r.tickets_base}))}/><p className="chart-caption">If incremental CPA is unknown, this line correctly stays flat: budget alone is not evidence of additional sales.</p></Panel>
   </div>

   <div className="two-columns section-gap">
    <Panel title="Where the selected budget should be tested" aside={<SourceBadge source={result.marketing_plan.classification}/>}><Table><thead><tr><th>Rank</th><th>Place</th><th>Score</th><th>Share</th><th>Budget</th><th>Expected ad tickets</th></tr></thead><tbody>{result.marketing_plan.geographies.map(g=><tr key={g.id}><td>#{g.rank}</td><td>{g.name}<small>{g.confidence} confidence</small></td><td>{number(g.score)}/100</td><td>{number(g.recommended_share_pct)}%</td><td>{money(g.recommended_budget_cents)}</td><td>{number(g.expected_incremental_tickets)}</td></tr>)}</tbody></Table><p className="microcopy section-gap">{result.marketing_plan.recommendation}</p></Panel>
    <Panel title="Which screening should receive support?" aside={<SourceBadge source="MODEL ESTIMATE"/>}><Table><thead><tr><th>Screening</th><th>Risk</th><th>Priority</th><th>Forecast gap</th><th>Budget</th></tr></thead><tbody>{result.marketing_plan.screenings.map(s=><tr key={s.screening_id}><td>{shortDate(s.date)}</td><td><SourceBadge source={s.risk}/></td><td>{s.priority_score}/100</td><td>{number(s.forecast_shortfall)}</td><td>{money(s.recommended_budget_cents)}</td></tr>)}</tbody></Table></Panel>
   </div>

   <Panel title="Price ladder" className="section-gap"><Table><thead><tr><th>Price</th><th>Expected tickets</th><th>Occupancy</th><th>Gross revenue</th><th>{number(result.attendance_target_pct)}% target</th></tr></thead><tbody>{result.price_ladder.map(row=><tr key={row.ticket_price_cents}><td>{money(row.ticket_price_cents)}</td><td>{number(row.tickets_base)}</td><td>{percent(row.occupancy_base_pct)}</td><td>{money(row.gross_revenue_base_cents)}</td><td><SourceBadge source={row.meets_target?'MEETS TARGET':'BELOW TARGET'}/></td></tr>)}</tbody></Table></Panel>

   <Panel title="Selected screenings" className="section-gap"><Table><thead><tr><th>Screening</th><th>Baseline</th><th>Price-adjusted</th><th>Ad uplift</th><th>Expected</th><th>Occupancy</th><th>Gross revenue</th><th>Break-even vs €6.50 full house</th></tr></thead><tbody>{result.screenings.map(row=><tr key={row.id}><td>{weekday(row.date)} {shortDate(row.date)}</td><td>{number(row.baseline_base)}</td><td>{number(row.price_base)}</td><td>+{number(row.ad_increment_base)}</td><td><strong>{number(row.predicted_base)}</strong><small>{row.predicted_low}–{row.predicted_high}</small></td><td>{percent(row.occupancy_base_pct)}</td><td>{money(row.gross_revenue_base_cents)}</td><td>{number(row.break_even_tickets_vs_baseline_full)} tickets</td></tr>)}</tbody></Table></Panel>

   <Panel title="Warnings & assumptions" className="section-gap" aside={<SourceBadge source="TRANSPARENT MODEL"/>}><ul className="scenario-warning-list">{result.warnings.map(w=><li key={w}>{w}</li>)}</ul><div className="scenario-model-meta"><div><span>Historical rows</span><strong>{number(d.forecast_model.rows)}</strong></div><div><span>Unique historical events</span><strong>{number(d.forecast_model.unique_events)}</strong></div><div><span>Grouped validation MAE</span><strong>{d.forecast_model.validation?.mae_tickets==null?'—':`${number(d.forecast_model.validation.mae_tickets)} tickets`}</strong></div><div><span>Occupancy MAE</span><strong>{d.forecast_model.validation?.mae_occupancy_pp==null?'—':`${number(d.forecast_model.validation.mae_occupancy_pp)} pp`}</strong></div></div>{d.forecast_model.sources?.length?<div className="scenario-sources"><strong>Historical ESO source URLs</strong><p>These archived programme pages are the provenance for the baseline inventory observations.</p><div>{d.forecast_model.sources.map((url,index)=><a key={url} href={url} target="_blank" rel="noreferrer">ESO source {index+1}</a>)}</div></div>:null}</Panel>
  </>}
 </>;
}

function Field({label,value,set,min,max,step,placeholder}:{label:string;value:string;set:(value:string)=>void;min?:string;max?:string;step?:string;placeholder?:string}){return <div className="field"><Label>{label}</Label><Input type="number" value={value} onChange={e=>set(e.target.value)} min={min} max={max} step={step} placeholder={placeholder}/></div>}
function EvidenceRow({label,source}:{label:string;source?:SourceLabel}){return <div className="data-detail"><span>{label}</span>{source?<SourceBadge source={source}/>:<span>—</span>}</div>}
function ScenarioChart({data,target}:{data:{x:number;tickets:number;revenue:number}[];target:number}){return <div className="chart"><ResponsiveContainer width="100%" height="100%"><LineChart data={data} margin={{top:12,right:18,left:-15,bottom:8}}><CartesianGrid stroke="#eaf0f3" vertical={false}/><XAxis dataKey="x" tickFormatter={v=>`€${v}`} tick={{fontSize:11}}/><YAxis yAxisId="tickets" domain={[0,'auto']} tick={{fontSize:11}}/><YAxis yAxisId="revenue" orientation="right" domain={[0,'auto']} tick={{fontSize:11}} tickFormatter={v=>`€${v}`}/><Tooltip formatter={(v:any,name:any)=>String(name)==='tickets'?[Number(v),'Expected tickets']:[`€${Number(v).toFixed(0)}`,'Gross revenue']} labelFormatter={v=>`Ticket price €${v}`}/><ReferenceLine yAxisId="tickets" y={target} strokeDasharray="4 4"/><Line yAxisId="tickets" type="monotone" dataKey="tickets" stroke="#008e94" strokeWidth={3} dot={{r:3}}/><Line yAxisId="revenue" type="monotone" dataKey="revenue" stroke="#173957" strokeWidth={2} strokeDasharray="4 3" dot={false}/></LineChart></ResponsiveContainer></div>}
function BudgetChart({data}:{data:{x:number;tickets:number}[]}){return <div className="chart"><ResponsiveContainer width="100%" height="100%"><LineChart data={data} margin={{top:12,right:18,left:-15,bottom:8}}><CartesianGrid stroke="#eaf0f3" vertical={false}/><XAxis dataKey="x" tickFormatter={v=>`€${v}`} tick={{fontSize:11}}/><YAxis domain={[0,'auto']} tick={{fontSize:11}}/><Tooltip formatter={(v:any)=>[Number(v),'Expected tickets']} labelFormatter={v=>`Advertising budget €${v}`}/><Line type="monotone" dataKey="tickets" stroke="#008e94" strokeWidth={3} dot={{r:3}}/></LineChart></ResponsiveContainer></div>}
