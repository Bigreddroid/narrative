const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1400, height: 900 } });
  const page = await ctx.newPage();

  // Go directly to the world view page
  await page.goto('http://localhost:5173', { waitUntil: 'networkidle', timeout: 30000 });
  
  // Wait for the page to fully load
  await page.waitForTimeout(3000);
  
  // Click the World View tab if it exists
  try {
    const worldTab = page.getByText('World View');
    if (await worldTab.count() > 0) {
      await worldTab.first().click();
      await page.waitForTimeout(8000); // Wait for D3 + CDN topojson
    }
  } catch(e) {
    console.log('No World View tab click needed, err:', e.message.slice(0, 60));
    await page.waitForTimeout(8000);
  }

  await page.screenshot({ path: 'D:\Narrative v5\ss_world_dark.png', fullPage: false });
  console.log('dark done');

  // Toggle theme
  try {
    await page.click('[title*="theme"], button[title*="Light"], button[title*="Dark"]');
    await page.waitForTimeout(2000);
  } catch(e) {
    console.log('no theme toggle found:', e.message.slice(0,60));
  }

  await page.screenshot({ path: 'D:\Narrative v5\ss_world_light.png', fullPage: false });
  console.log('light done');

  await browser.close();
})();
