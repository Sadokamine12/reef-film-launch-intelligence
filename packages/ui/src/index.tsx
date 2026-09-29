'use client';
import * as React from 'react';
import {Slot} from '@radix-ui/react-slot';
import * as DialogPrimitive from '@radix-ui/react-dialog';
import {cva,type VariantProps} from 'class-variance-authority';
import {clsx,type ClassValue} from 'clsx';
import {twMerge} from 'tailwind-merge';
export function cn(...inputs:ClassValue[]){return twMerge(clsx(inputs));}
const buttonVariants=cva('button',{variants:{variant:{default:'button-primary',outline:'button-outline',ghost:'button-ghost',danger:'button-danger'},size:{default:'',sm:'button-sm',icon:'button-icon'}},defaultVariants:{variant:'default',size:'default'}});
export function Button({className,variant,size,asChild=false,...props}:React.ComponentProps<'button'>&VariantProps<typeof buttonVariants>&{asChild?:boolean}){const Comp=asChild?Slot:'button';return <Comp className={cn(buttonVariants({variant,size}),className)} {...props}/>;}
export function Card({className,...props}:React.ComponentProps<'section'>){return <section className={cn('card',className)} {...props}/>;}
export function CardHeader({className,...props}:React.ComponentProps<'div'>){return <div className={cn('card-header',className)} {...props}/>;}
export function CardTitle({className,...props}:React.ComponentProps<'h2'>){return <h2 className={cn('card-title',className)} {...props}/>;}
export function CardContent({className,...props}:React.ComponentProps<'div'>){return <div className={cn('card-content',className)} {...props}/>;}
export function Badge({className,...props}:React.ComponentProps<'span'>){return <span className={cn('badge',className)} {...props}/>;}
export function Input({className,...props}:React.ComponentProps<'input'>){return <input className={cn('input',className)} {...props}/>;}
export function Textarea({className,...props}:React.ComponentProps<'textarea'>){return <textarea className={cn('input textarea',className)} {...props}/>;}
export function Label({className,...props}:React.ComponentProps<'label'>){return <label className={cn('label',className)} {...props}/>;}
export function Select({className,...props}:React.ComponentProps<'select'>){return <select className={cn('input select',className)} {...props}/>;}
export function Table({className,...props}:React.ComponentProps<'table'>){return <div className="table-scroll"><table className={cn('table',className)} {...props}/></div>;}
export function Progress({value,label}:{value:number;label:string}){return <div className="progress" role="progressbar" aria-label={label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.min(100,Math.max(0,value))}><div style={{width:`${Math.min(100,Math.max(0,value))}%`}}/></div>;}
export const Dialog=DialogPrimitive.Root;
export const DialogTrigger=DialogPrimitive.Trigger;
export const DialogClose=DialogPrimitive.Close;
export const DialogTitle=DialogPrimitive.Title;
export const DialogDescription=DialogPrimitive.Description;
export function DialogContent({className,children,...props}:React.ComponentProps<typeof DialogPrimitive.Content>){return <DialogPrimitive.Portal><DialogPrimitive.Overlay className="dialog-overlay"/><DialogPrimitive.Content className={cn('dialog-content',className)} {...props}>{children}<DialogPrimitive.Close className="dialog-x" aria-label="Close dialog">×</DialogPrimitive.Close></DialogPrimitive.Content></DialogPrimitive.Portal>;}
