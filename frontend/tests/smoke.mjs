import assert from 'node:assert/strict'
import puppeteer from 'puppeteer-core'

const baseURL = process.env.BASE_URL || 'http://127.0.0.1:5173'
const executablePath = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe'
const browser = await puppeteer.launch({ executablePath, headless: true })

async function openPage(path, width = 1280) {
  const page = await browser.newPage()
  await page.setViewport({ width, height: 800 })
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  await page.goto(`${baseURL}${path}`, { waitUntil: 'networkidle0' })
  assert.deepEqual(errors, [], `页面脚本错误：${errors.join('；')}`)
  return page
}

async function fill(page, selector, value) {
  await page.evaluate(selector => { const element = document.querySelector(selector); if (element) element.value = '' }, selector)
  await page.type(selector, value)
}

async function clickButton(page, text) {
  const clicked = await page.evaluate(label => {
    const button = [...document.querySelectorAll('button')].find(item => item.textContent?.includes(label))
    if (!button) return false
    button.click()
    return true
  }, text)
  assert.ok(clicked, `找不到按钮：${text}`)
}

try {
  const player = await openPage('/dashboard?preview=player')
  await player.waitForFunction(() => !document.querySelector('.topbar')?.textContent?.includes('正在读取比赛'))
  const initialScore = await player.$eval('.score-plate__figure', element => Number(element.textContent))
  await fill(player, '#flag-input', 'flag{t02-web-r24}')
  await clickButton(player, '提交验判')
  await player.waitForFunction(() => document.querySelector('.submission-feedback')?.textContent?.includes('有效攻击'))
  await player.waitForSelector('.flag-feedback-dialog', { visible: true })
  assert.ok((await player.$eval('.flag-feedback-dialog', element => element.textContent)).includes('Flag 正确'), '有效 Flag 应弹出成功提示')
  await clickButton(player, '知道了')
  await player.waitForSelector('.flag-feedback-dialog', { hidden: true })
  await player.waitForFunction(expected => Number(document.querySelector('.score-plate__figure')?.textContent) === expected, {}, initialScore + 100)
  const acceptedScore = await player.$eval('.score-plate__figure', element => Number(element.textContent))
  assert.equal(acceptedScore, initialScore + 100, '有效攻击应加 100 分')
  await fill(player, '#flag-input', 'flag{t02-web-r24}')
  await clickButton(player, '提交验判')
  await player.waitForFunction(() => document.querySelector('.submission-feedback')?.textContent?.includes('重复提交'))
  await player.waitForSelector('.flag-feedback-dialog', { visible: true })
  assert.ok((await player.$eval('.flag-feedback-dialog', element => element.textContent)).includes('重复提交'), '重复 Flag 应弹出失败提示')
  await clickButton(player, '知道了')
  await player.waitForSelector('.flag-feedback-dialog', { hidden: true })
  const duplicateScore = await player.$eval('.score-plate__figure', element => Number(element.textContent))
  assert.equal(duplicateScore, acceptedScore, '重复提交不应改变分数')
  await player.setViewport({ width: 375, height: 800 })
  await new Promise(resolve => setTimeout(resolve, 250))
  const mobileWidth = await player.evaluate(() => document.documentElement.scrollWidth)
  assert.ok(mobileWidth <= 375, `移动端页面宽度 ${mobileWidth} 超出 375`)
  await player.close()
  console.log('PASS 选手有效攻击、重复提交去重、比赛计时与移动端宽度')

  const admin = await openPage('/admin/teams?preview=admin')
  await clickButton(admin, '新建队伍')
  await admin.waitForSelector('.dialog-form', { visible: true })
  await fill(admin, '#team-no', '11')
  await fill(admin, '#team-name', '测试队')
  await clickButton(admin, '保存队伍')
  await admin.waitForFunction(() => document.querySelector('.data-table')?.textContent?.includes('测试队'))
  const adminRowText = await admin.evaluate(() => [...document.querySelectorAll('.data-table tbody tr')].find(row => row.textContent?.includes('测试队'))?.textContent)
  assert.ok(adminRowText?.includes('测试队'), '新建队伍应出现在队伍列表')
  assert.ok(adminRowText?.includes('/ 4'), '队伍管理应显示人员数量')
  assert.ok(!adminRowText?.includes('1000'), '队伍管理只做人员管理，不应显示积分')
  assert.ok(!adminRowText?.includes('初始化分数'), '队伍管理不应包含积分操作')
  await admin.close()
  console.log('PASS 管理员新建队伍与人员管理')

  const match = await openPage('/admin/match?preview=admin')
  await clickButton(match, '暂停比赛')
  await match.waitForFunction(() => document.querySelector('.topbar')?.textContent?.includes('已暂停'))
  const pausedClock = await match.$eval('.match-clock .num', element => element.textContent)
  assert.notEqual(pausedClock, '00:00:00', '暂停时应保留剩余时间')
  await clickButton(match, '恢复比赛')
  await match.waitForFunction(() => document.querySelector('.topbar')?.textContent?.includes('进行中'))
  await match.close()
  console.log('PASS 比赛暂停计时保留与恢复')
} finally {
  await browser.close()
}
