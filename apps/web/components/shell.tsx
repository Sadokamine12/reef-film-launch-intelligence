'use client';
import {useState,createContext,useContext} from 'react';
import {usePathname} from 'next/navigation';
import Link from 'next/link';
import {LayoutDashboard,Ticket,Megaphone,MapPin,Layers3,Palette,FileChartColumn,Settings,ChevronRight,Menu,X,LogOut,Orbit} from 'lucide-react';
import {NAV_ITEMS} from '@reef/config';
import type {User} from '@reef/types';
import {useResource} from '@/lib/hooks';
import {api} from '@/lib/api';
const UserContext=createContext<User|null>(null);
export const useUser=()=>useContext(UserContext);
const icons={dashboard:LayoutDashboard,tickets:Ticket,marketing:Megaphone,geography:MapPin,campaigns:Layers3,creatives:Palette,reports:FileChartColumn,settings:Settings};
export function Shell({children}:{children:React.ReactNode}){const pathname=usePathname();if(pathname==='/login')return children;return <Workspace>{children}</Workspace>;}
function Workspace({children}:{children:React.ReactNode}){
 const pathname=usePathname();const [open,setOpen]=useState(false);const {data:user}=useResource<User>('/auth/me');
 return <UserContext.Provider value={user}><div className="app-shell"><aside className={`sidebar ${open?'is-open':''}`}>
 <Link href="/" className="brand"><Orbit size={30} strokeWidth={1.4}/><span><strong>REEF</strong><span>Distribution</span></span></Link>
 <button className="mobile-close" aria-label="Close navigation" onClick={()=>setOpen(false)}><X/></button>
 <div className="workspace-label">LAUNCH INTELLIGENCE</div>
 <nav aria-label="Main navigation">{NAV_ITEMS.map(item=>{const Icon=icons[item.icon];const active=pathname===item.href;return <Link key={item.href} href={item.href} onClick={()=>setOpen(false)} className={`nav-item ${active?'active':''}`} aria-current={active?'page':undefined}><Icon size={19}/><span>{item.label}</span>{active&&<ChevronRight size={15}/>}</Link>;})}</nav>
 <div className="sidebar-project"><div className="tiny-label">CURRENT LAUNCH</div><strong>Resolution</strong><p>ESO Supernova · February 2027</p><div className="sidebar-dates">02 <span>/</span> 09 <span>/</span> 16 <span>/</span> 23</div></div>
 <div className="sidebar-footer"><span className="avatar">R</span><div><strong>REEF workspace</strong><small>{user?.role==='editor'?'Management team':'View access'}</small></div><button aria-label="Sign out" onClick={async()=>{await api('/auth/logout',{method:'POST'});window.location.assign('/login');}}><LogOut size={17}/></button></div>
 </aside>{open&&<button className="nav-overlay" aria-label="Close navigation" onClick={()=>setOpen(false)}/>}
 <div className="main-shell"><header className="topbar"><div className="breadcrumbs"><button className="mobile-menu" aria-label="Open navigation" onClick={()=>setOpen(true)}><Menu/></button><span>Launch workspace</span><ChevronRight size={14}/><strong>Resolution</strong></div><div className="topbar-right"><span className="venue"><MapPin size={15}/>ESO Supernova, Garching</span><span className="topbar-divider"/><span className="avatar light">MT</span><span>Management team</span></div></header>
 {user?.development&&<div className="development-label">LOCAL DEVELOPMENT · Sign-in bypass enabled for local verification</div>}
 <main id="main-content" className="main-content">{children}</main><footer className="page-footer"><span>REEF Launch Intelligence</span><span>Every decision starts with evidence.</span></footer></div></div></UserContext.Provider>;
}
