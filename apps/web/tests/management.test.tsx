import React from 'react';
import {describe,it,expect,afterEach} from 'vitest';
import {render,screen,cleanup} from '@testing-library/react';
import {Metric,StatusBadge,Feedback} from '../components/shared';
import {money,number,shortDate} from '../lib/format';
afterEach(cleanup);
describe('Management presentation',()=>{
 it('distinguishes unknown sales from observed zero',()=>{expect(number(null)).toBe('—');expect(number(0)).toBe('0');});
 it('displays cents without silently rounding the campaign cap',()=>{expect(money(1999)).toBe('€19.99');expect(money(0)).toBe('€0');expect(money(null)).toBe('—');});
 it('renders the February screening date without timezone rollover',()=>{expect(shortDate('2027-02-02')).toBe('02 Feb');});
 it('exposes status as readable text rather than color alone',()=>{render(<StatusBadge status="NEAR_FULL"/>);expect(screen.getByText('NEAR FULL')).toBeVisible();});
 it('shows unknown ticket counts explicitly',()=>{render(<Metric label="Tickets sold" value={number(null)} detail="Awaiting an observation"/>);expect(screen.getByText('—')).toBeVisible();expect(screen.getByText('Awaiting an observation')).toBeVisible();});
 it('announces save errors without success feedback',()=>{render(<Feedback error="Budget ceiling reached" success="Saved"/>);expect(screen.getByRole('alert')).toHaveTextContent('Budget ceiling reached');expect(screen.queryByText('Saved')).toBeNull();});
});
