import assert from 'node:assert/strict'
import puppeteer from 'puppeteer-core'

const baseURL = process.env.INTEGRATION_URL || 'http://127.0.0.1:5174'
const executablePath = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe'
const browser = await puppeteer.launch({ executablePath, headless: true })
const page = await browser.newPage()
await page.setViewport({ width: 1280, height: 800 })
const errors = []
page.on('pageerror', error => errors.push(error.message))

async function login(username, password) {
  await page.goto(`${baseURL}/login`, { waitUntil: 'networkidle0' })
  await page.evaluate(() => { for (const selector of ['#username', '#password']) { const input = document.querySelector(selector); if (input) input.value = '' } })
  await page.type('#username', username)
  await page.type('#password', password)
  await page.click('.login-submit')
  await page.waitForFunction(expected => location.pathname === expected || location.pathname === '/dashboard', {}, username === 'admin' ? '/admin' : '/dashboard')
  await page.waitForFunction(() => !document.querySelector('.topbar')?.textContent?.includes('正在读取比赛'))
}

try {
  await login('admin', 'Admin123!')
  await page.waitForFunction(() => document.querySelector('.stat-row')?.textContent?.includes('9'))
  const adminText = await page.$eval('#main-content', element => element.textContent)
  assert.ok(adminText.includes('运行总览') && adminText.includes('异常靶机'), '管理总览数据未渲染')
  const session = await page.createCDPSession()
  await session.send('Network.clearBrowserCookies')

  await login('player1', 'Player123!')
  await page.waitForSelector('.score-plate__figure')
  const before = await page.$eval('.score-plate__figure', element => Number(element.textContent))
  await page.type('#flag-input', 'flag{not-a-real-flag}')
  await page.click('.flag-form button[type="submit"]')
  await page.waitForFunction(() => document.querySelector('.submission-feedback')?.textContent?.includes('无效 Flag'))
  const after = await page.$eval('.score-plate__figure', element => Number(element.textContent))
  assert.equal(after, before, '无效 Flag 不应改变真实后端分数')
  await page.click('a[href="/scoreboard"]')
  await page.waitForFunction(() => location.pathname === '/scoreboard' && document.querySelectorAll('.scoreboard-table tbody tr').length >= 3)
  const services = await page.$$eval('.scoreboard-table tbody tr:first-child .service-state', elements => elements.map(element => element.textContent))
  assert.ok(services.length === 3, '计分板应显示每个服务的状态')
  assert.deepEqual(errors, [], `浏览器脚本错误：${errors.join('；')}`)
  console.log('PASS 真实后端管理员总览、选手登录、无效Flag、实时计分板')
} finally {
  await browser.close()
}
