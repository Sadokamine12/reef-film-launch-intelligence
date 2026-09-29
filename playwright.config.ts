import {defineConfig,devices} from '@playwright/test';
export default defineConfig({
 testDir:'./tests/e2e',fullyParallel:false,workers:1,timeout:30000,
 reporter:[['list'],['html',{open:'never'}]],
 use:{baseURL:'http://127.0.0.1:3000',trace:'retain-on-failure',screenshot:'only-on-failure'},
 projects:[{name:'chromium',use:{...devices['Desktop Chrome'],viewport:{width:1600,height:1000},launchOptions:process.env.REEF_CHROMIUM_PATH?{executablePath:process.env.REEF_CHROMIUM_PATH,args:['--no-sandbox','--disable-dev-shm-usage','--use-gl=angle','--use-angle=swiftshader']}:{}}}],
 webServer:[
  {command:'.venv/bin/python scripts/start-e2e-api.py',url:'http://127.0.0.1:8000/health/ready',reuseExistingServer:false,timeout:60000},
  {command:'npm run start -w @reef/web -- --port 3000',url:'http://127.0.0.1:3000/login',reuseExistingServer:false,timeout:60000,env:{API_BASE_URL:'http://127.0.0.1:8000',APP_ORIGIN:'http://127.0.0.1:3000'}}
 ]
});
