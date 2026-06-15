const { chromium } = require('playwright');
(async () => {
  const BASE = 'http://127.0.0.1:5173';
  // Real token via dev-login through the vite proxy (-> WSL backend, real data)
  const res = await fetch(BASE + '/api/v1/auth/dev-login', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: 'demo@narrative.local', password: 'x' })
  });
  const { access_token } = await res.json();
  console.log('token len', (access_token || '').length);

  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await ctx.addInitScript((tok) => {
    localStorage.setItem('narrative_token', tok);
    localStorage.setItem('narrative_user', JSON.stringify({ id: 'demo', email: 'demo@narrative.local', tier: 'pro', name: 'Demo', city: 'Mumbai', country: 'India' }));
  }, access_token);
  const page = await ctx.newPage();
  page.on('pageerror', e => console.log('THROW', e.message.slice(0, 110)));

  await page.goto(BASE + '/world', { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(6500);
  await page.screenshot({ path: 'D:/Narrative v5/ss_real_world.png' });
  console.log('world shot done');

  await page.goto(BASE + '/world?tab=feed', { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(4000);
  await page.screenshot({ path: 'D:/Narrative v5/ss_real_feed.png' });
  console.log('feed shot done');

  let eid = null;
  try {
    const f = await (await fetch(BASE + '/api/v1/feed/', { headers: { Authorization: 'Bearer ' + access_token } })).json();
    eid = f.feed && f.feed[0] && f.feed[0].id;
    console.log('feed items', (f.feed || []).length, 'first', eid);
  } catch (e) { console.log('feed fetch err', e.message.slice(0, 80)); }
  if (eid) {
    await page.goto(BASE + '/event/' + eid, { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(4500);
    await page.screenshot({ path: 'D:/Narrative v5/ss_real_event.png' });
    console.log('event shot done');
  }

  await page.goto(BASE + '/', { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(3000);
  await page.screenshot({ path: 'D:/Narrative v5/ss_real_landing.png' });
  console.log('landing shot done');

  await browser.close();
})().catch(e => { console.error('ERR', e.message); process.exit(1); });
