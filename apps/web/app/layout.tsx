import type {Metadata} from 'next';
import {Shell} from '@/components/shell';
import './globals.css';
export const metadata:Metadata={title:{default:'REEF Launch Intelligence',template:'%s · REEF'},description:'Ticket sales and marketing decisions for REEF Distribution.',robots:{index:false,follow:false}};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="en"><body><a href="#main-content" className="skip-link">Skip to content</a><Shell>{children}</Shell></body></html>;}
