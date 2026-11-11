import asyncio, json
from playwright.async_api import async_playwright
async def run(base):
 async with async_playwright() as p:
  browser=await p.chromium.launch(headless=True)
  page=await browser.new_page(accept_downloads=True)
  errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  await page.goto(base)
  assert await page.locator('#entrance').is_visible()
  await page.click('#explore')
  assert await page.locator('#map > article').count()==4
  await page.locator('[data-node-id="practice"] button',has_text='+ One repetition').click()
  assert '1 repetition' in await page.locator('[data-node-id="practice"]').inner_text()
  await page.get_by_role('button',name='Open Build a place',exact=True).click()
  await page.click('#add')
  await page.locator('[name="title"]').fill('My nested experience')
  await page.locator('[name="body"]').fill('<img src=x onerror=alert(1)>')
  await page.locator('[name="kind"]').select_option('counter')
  await page.get_by_role('button',name='Keep this place').click()
  assert await page.locator('#map img').count()==0
  await page.get_by_role('button',name='Open My nested experience',exact=True).click()
  await page.get_by_role('button',name='+ One repetition',exact=True).click()
  before=await page.evaluate('window.zenGarden.inspect().garden')
  async with page.expect_download() as info: await page.click('#save')
  dl=await info.value
  with open(await dl.path()) as f: exported=json.load(f)
  assert exported==before
  await page.reload();await page.click('#explore')
  assert await page.evaluate('window.zenGarden.inspect().garden')==before
  await page.locator('#trail button').first.click()
  page.once('dialog',lambda d:d.accept())
  await page.locator('#file').set_input_files({'name':'garden.json','mimeType':'application/json','buffer':json.dumps(exported).encode()})
  await page.wait_for_function('document.querySelector("#status").textContent === "Garden restored."')
  assert await page.evaluate('window.zenGarden.inspect().garden')==before
  await page.locator('#file').set_input_files({'name':'bad.json','mimeType':'application/json','buffer':b'{"version":99}'})
  await page.wait_for_function('document.querySelector("#status").textContent.startsWith("Could not load")')
  assert await page.evaluate('window.zenGarden.inspect().garden')==before
  await page.set_viewport_size({'width':390,'height':844})
  assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth')
  await page.evaluate('window.zenGarden.dispatch({type:"focus",id:"purpose"})')
  await page.locator('#address').fill('2')
  await page.locator('#address-form button').click()
  assert await page.evaluate('window.zenGarden.inspect().garden.focus')=='practice'
  await page.evaluate('window.zenGarden.dispatch({type:"focus",id:"build"})')
  page.once('dialog',lambda d:d.accept())
  await page.locator('#map > article.center').get_by_role('button',name='Remove',exact=True).click()
  assert await page.evaluate('window.zenGarden.inspect().garden.focus')=='purpose'
  assert not errors,errors
  await browser.close()
  return 'PASS: entrance, nested creation, repetition, inert HTML, export, local reload, import restoration, invalid-import rollback, mobile overflow, address navigation, subtree removal; zero page errors.'

if __name__ == '__main__':
 import sys
 print(asyncio.run(run(sys.argv[1] if len(sys.argv)>1 else 'http://localhost:8000/candidates/perplexity/')))
