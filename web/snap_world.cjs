const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });

  await ctx.addInitScript(() => {
    localStorage.setItem('narrative_user', JSON.stringify({ id: 1, email: 'demo@narrative.io', tier: 'paid', name: 'Demo' }));
    localStorage.setItem('narrative_token', 'dev-token');
  });

  const page = await ctx.newPage();
  // Stub API responses so page doesn't hang on backend
  await page.route('**/api/**', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ feed: [], events: [] }) }));

  // Capture console errors
  page.on('console', msg => { if (msg.type() === 'error') console.log('PAGE ERR:', msg.text().slice(0, 120)); });
  page.on('pageerror', err => console.log('PAGE THROW:', err.message.slice(0, 120)));

  // Go directly to /world (PrivateRoute DEV_BYPASS passes in Vite dev mode)
  await page.goto('http://localhost:5173/world', { waitUntil: 'networkidle', timeout: 20000 });
  await page.waitForTimeout(3000);

  // Take a diagnostic screenshot to see what rendered
  await page.screenshot({ path: 'D:/Narrative v5/ss_debug.png' });
  const title = await page.title();
  const bodyText = await page.locator('body').textContent();
  console.log('page title:', title);
  console.log('body text (first 200):', bodyText.trim().slice(0, 200));

  // Wait for D3 + topojson CDN load (generous timeout)
  await page.waitForTimeout(10000);

  await page.screenshot({ path: 'D:/Narrative v5/ss_web_worldview_dark.png' });
  console.log('dark done');

  // Toggle theme — look for a button with title containing "theme", "light", or "dark"
  try {
    const allBtns = await page.locator('button[title]').all();
    for (const btn of allBtns) {
      const t = (await btn.getAttribute('title') || '').toLowerCase();
      if (t.includes('theme') || t.includes('light') || t.includes('dark') || t.includes('mode')) {
        await btn.click();
        console.log('toggled theme via button title:', t);
        break;
      }
    }
    await page.waitForTimeout(2000);
  } catch (e) {
    console.log('theme toggle failed:', e.message.slice(0, 60));
  }

  await page.screenshot({ path: 'D:/Narrative v5/ss_web_worldview_light.png' });
  console.log('light done');

  await browser.close();
})().catch(e => { console.error(e.message); process.exit(1); });
