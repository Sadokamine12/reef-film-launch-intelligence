import {test,expect} from '@playwright/test';
const routes=[['Ticket Sales','/ticket-sales','Forecast the finish, not just today'],['Forecast & Scenarios','/scenarios','Resolution decision lab'],['Marketing','/marketing','Separate what-if allocation from spend today'],['Geography','/geography','Market-test priority that learns from evidence'],['Campaigns','/campaigns','Plan, measure, then decide'],['Creatives','/creatives','Two ideas. One ticket decision.'],['Reports','/reports','The numbers. The decision. The next step.'],['Settings','/settings','A clear source of truth']] as const;
test('honest seeded command center and all navigation routes',async({page})=>{
 await page.goto('/');await expect(page.getByRole('heading',{name:'Ticket Sales Command Center'})).toBeVisible();
 await expect(page.getByText('WHAT SHOULD WE DO TODAY?')).toBeVisible();
 await expect(page.getByRole('heading',{name:'Spend €0 today. Prepare the ticket-sales launch.'})).toBeVisible();
 await page.waitForTimeout(1800);await page.screenshot({path:'test-results/dashboard-desktop.png',fullPage:true});
 for(const [label,route,title] of routes){await page.getByRole('navigation').getByRole('link',{name:label,exact:true}).click();await expect(page).toHaveURL(new RegExp(route));await expect(page.getByRole('heading',{name:title,exact:true})).toBeVisible();}
});
test('records a real ticket observation and refreshes the forecast',async({page})=>{
 await page.goto('/ticket-sales');await page.getByRole('button',{name:'Record ticket sales'}).click();
 await page.getByLabel('Total tickets sold',{exact:true}).fill('12');await page.getByLabel('Source / note').fill('E2E verified test observation; isolated test database');
 await page.getByRole('button',{name:'Save observation'}).click();await expect(page.getByRole('dialog')).not.toBeVisible();
 await expect(page.getByRole('cell',{name:'12 / 109'})).toBeVisible();await page.reload();await expect(page.getByRole('cell',{name:'12 / 109'})).toBeVisible();
});
test('creates and edits a creative with persisted copy',async({page})=>{
 await page.goto('/creatives');await page.getByRole('button',{name:'New creative'}).click();
 await page.getByLabel('Name',{exact:true}).fill('Creative C — E2E');await page.getByLabel('Headline').fill('A Tuesday to remember');await page.getByLabel('Body copy').fill('Resolution at ESO. Test creative for the isolated E2E database.');
 await page.getByRole('button',{name:'Save creative'}).click();await expect(page.getByRole('heading',{name:'Creative C — E2E'})).toBeVisible();await page.reload();await expect(page.getByRole('heading',{name:'A Tuesday to remember'})).toBeVisible();
});
test('campaign CSV preview, save and report export use the API',async({page})=>{
 await page.goto('/campaigns');await page.getByRole('button',{name:'New campaign',exact:true}).click();
 await page.getByLabel('Campaign name').fill('E2E Local Test');const today=new Date().toISOString().slice(0,10);
 await page.getByLabel('Start date',{exact:true}).fill(today);await page.getByLabel('End date',{exact:true}).fill(today);
 await page.getByRole('button',{name:'Save campaign draft'}).click();await expect(page.getByRole('cell',{name:'E2E Local Test',exact:false})).toBeVisible();
 await page.getByRole('button',{name:'Import CSV'}).click();
 await page.getByLabel('Meta / Google / normalized CSV').setInputFiles({name:'e2e.csv',mimeType:'text/csv',buffer:Buffer.from(`date,spend_eur,impressions,clicks,landing_page_views,attributed_tickets\n${today},9.50,1000,30,20,2`)});
 await page.getByRole('button',{name:'Preview import'}).click();await expect(page.getByText('1 daily rows · €9.50 total observed spend')).toBeVisible();await page.getByRole('button',{name:'Save 1 observations'}).click();await expect(page.getByRole('dialog')).not.toBeVisible();
 await expect(page.getByText('€4.75 / ticket')).toBeVisible();await page.goto('/reports');await page.getByRole('button',{name:'Campaign performance',exact:true}).click();await expect(page.getByRole('cell',{name:'E2E Local Test',exact:true})).toBeVisible();
 const download=page.waitForEvent('download');await page.getByRole('link',{name:'Export CSV'}).click();expect((await download).suggestedFilename()).toBe('reef-campaigns.csv');
});
test('business rule changes persist and invalid ceilings are rejected',async({page})=>{
 await page.goto('/settings');await page.getByLabel('Stop ads at (tickets)').fill('96');await page.getByRole('button',{name:'Save business rules'}).click();await page.reload();await expect(page.getByLabel('Stop ads at (tickets)')).toHaveValue('96');
 await page.getByLabel('Meta ceiling (€)').fill('450');await page.getByRole('button',{name:'Save business rules'}).click();await expect(page.locator('.form-error')).toContainText('exceed the total ceiling');
});
test('mobile navigation stays usable without horizontal overflow',async({page})=>{
 await page.setViewportSize({width:390,height:844});await page.goto('/');await expect(page.getByRole('heading',{name:'Ticket Sales Command Center'})).toBeVisible();
 await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
 await page.getByRole('button',{name:'Open navigation'}).click();await page.getByRole('navigation').getByRole('link',{name:'Geography',exact:true}).click();await expect(page.getByRole('heading',{name:'Market-test priority that learns from evidence'})).toBeVisible();await page.screenshot({path:'test-results/geography-mobile.png',fullPage:true});
});
