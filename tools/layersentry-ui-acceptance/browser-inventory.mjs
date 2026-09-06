import { chromium, firefox } from 'playwright'
import { createHash } from 'node:crypto'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'

// Read-only GUI baseline. No storageState, trace, HAR, request body or credential
// logging. A baseline pass is not provisioning/failover/production acceptance.
const output = path.resolve(process.env.LAYERSENTRY_GUI_EVIDENCE || 'evidence')
const username = process.env.LAYERSENTRY_GUI_USERNAME
const password = process.env.LAYERSENTRY_GUI_PASSWORD
const targets = (process.env.LAYERSENTRY_GUI_TARGETS || '10.10.10.14,10.10.10.20').split(',')
const routes = (process.env.LAYERSENTRY_GUI_ROUTES || 'dashboard,vm,volume,guestnetwork,template,event').split(',')
if (!routes.every(route => ['dashboard', 'vm', 'volume', 'guestnetwork', 'template', 'event', 'kubernetes-data-services'].includes(route))) {
  throw new Error('EXPLICIT_GUI_ROUTE_REQUIRED')
}
if (!username || !password || !targets.every(host => ['10.10.10.14', '10.10.10.20'].includes(host))) {
  throw new Error('EXPLICIT_LAB_IDENTITY_AND_TARGETS_REQUIRED')
}
await mkdir(output, { recursive: true, mode: 0o700 })
const results = []
for (const host of targets) {
  for (const [browserName, engine, options] of [
    ['chrome', chromium, { channel: 'chrome' }], ['firefox', firefox, {}]
  ]) {
    const record = { host, browser: browserName, capturedAt: new Date().toISOString(), status: 'FAILED', pages: [], blockedMutations: [], failedReads: [] }
    results.push(record)
    let browser
    let page
    let authenticated = false
    let stage = 'BROWSER_START'
    try {
      browser = await engine.launch({ ...options, headless: true })
      record.browserVersion = browser.version()
      const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, locale: 'en-US' })
      page = await context.newPage()
      record.rejectedRequests = []
      await page.exposeFunction('recordRequestRejection', detail => record.rejectedRequests.push(detail))
      await page.addInitScript(() => {
        window.addEventListener('unhandledrejection', event => {
          const error = event.reason
          const config = error?.config
          const safeIdentifier = value => String(value || '').replace(/[^A-Za-z0-9_]/g, '').slice(0, 80)
          // Deliberately omit config, URLs, payloads, headers and error stacks.
          window.recordRequestRejection({
            command: safeIdentifier(config?.params?.command || (typeof config?.data === 'string' ? new URLSearchParams(config.data).get('command') : config?.data?.get?.('command'))),
            code: safeIdentifier(error?.code),
            status: Number(error?.response?.status) || null
          })
        })
      })
      page.setDefaultTimeout(30000)
      page.setDefaultNavigationTimeout(45000)
      const pageErrors = []
      record.browserErrors = pageErrors
      page.on('pageerror', error => {
        const message = String(error.message).split(password).join('[redacted]').split(username).join('[redacted]')
          .replace(/([?&](?:sessionkey|apikey|secretkey|token|password)=)[^&\s]*/gi, '$1[redacted]')
        pageErrors.push({ name: error.name, message: message.slice(0, 1000) })
      })
      await context.route('**/client/api**', async route => {
        const request = route.request()
        const query = new URL(request.url()).searchParams
        const body = new URLSearchParams(request.postData() || '')
        const command = query.get('command') || body.get('command') || ''
        const capabilityProbe = command === 'forgotPassword' && !query.has('username') && !body.has('username')
        const knownRead = ['cloudianIsEnabled', 'readyForShutdown'].includes(command)
        if (!/^(?:list|get|find|query)[A-Z]/.test(command) && !['login', 'logout'].includes(command) && !capabilityProbe && !knownRead) {
          record.blockedMutations.push(command.replace(/[^A-Za-z0-9]/g, '').slice(0, 80))
          return route.abort('blockedbyclient')
        }
        await route.continue()
      })
      page.on('response', response => {
        const url = new URL(response.url())
        if (/\/client\/api\/?$/.test(url.pathname) && response.status() >= 400) {
          const body = new URLSearchParams(response.request().postData() || '')
          record.failedReads.push({ command: (url.searchParams.get('command') || body.get('command') || '').replace(/[^A-Za-z0-9]/g, '').slice(0, 80), status: response.status() })
        }
      })
      stage = 'LOGIN_PAGE'
      const response = await page.goto(`http://${host}:8080/client/#/user/login`)
      if (!response?.ok()) throw new Error('HTTP_FAILED')
      record.indexSha256 = createHash('sha256').update(await response.body()).digest('hex')
      stage = 'GUI_LOGIN'
      await page.locator('#formLogin input[autocomplete="username"], #formLogin input[placeholder="Username"]').first().fill(username)
      await page.locator('#formLogin input[type="password"]').first().fill(password)
      await page.locator('#formLogin button[type="submit"]').click()
      stage = 'GUI_LOGIN_REDIRECT'
      await page.waitForURL(/#\/dashboard(?:\?|$)/)
      stage = 'GUI_DASHBOARD_READY'
      await page.locator('.layout-content').first().waitFor({ state: 'visible' })
      authenticated = true
      for (const name of routes) {
        stage = `GUI_${name.toUpperCase()}`
        const errorsBefore = pageErrors.length
        const readsBefore = record.failedReads.length
        await page.goto(`http://${host}:8080/client/#/${name}`)
        await page.waitForLoadState('networkidle')
        const entry = { route: name, status: 'FAILED' }
        record.pages.push(entry)
        if (!page.url().includes(`#/${name}`)) throw new Error('ROUTE_REDIRECTED')
        if (name === 'kubernetes-data-services') {
          record.moduleTabs = []
          for (const tab of ['Kubernetes', 'DBaaS', 'APaaS']) {
            await page.getByRole('tab', { name: tab, exact: true }).click()
            const blocked = await page.getByText('Release qualification is still blocked', { exact: true }).isVisible()
            await page.screenshot({ path: path.join(output, `${host}-${browserName}-${tab}.png`), fullPage: true })
            record.moduleTabs.push({ module: tab, status: blocked ? 'BLOCKED' : 'NOT_VERIFIED' })
          }
          throw new Error('MODULE_LIFECYCLE_NOT_VERIFIED')
        }
        if (await page.locator('.ant-alert-error:visible').count()) throw new Error('VISIBLE_PAGE_ERROR')
        if (pageErrors.length > errorsBefore || record.failedReads.length > readsBefore) throw new Error('PAGE_READ_FAILED')
        const main = page.locator('main, [role="main"], .layout-content').first()
        await main.waitFor({ state: 'visible' })
        if (!(await main.innerText()).trim()) throw new Error('EMPTY_SHELL')
        await page.screenshot({ path: path.join(output, `${host}-${browserName}-${name}.png`), fullPage: true })
        entry.status = 'PASS'
      }
      stage = 'GUI_RUNTIME_AUDIT'
      if (record.blockedMutations.length) throw new Error('UNEXPECTED_MUTATION_ATTEMPT')
      if (pageErrors.length) throw new Error('BROWSER_RUNTIME_ERROR')
      record.status = 'READ_ONLY_GUI_BASELINE_PASS'
      record.productionReadiness = 'NOT_VERIFIED'
      await context.close()
    } catch (error) {
      record.failedStage = stage
      record.failureCode = /^[A-Z_]+$/.test(error.message) ? error.message : 'GUI_OPERATION_FAILED'
      if (authenticated && page) {
        await page.screenshot({ path: path.join(output, `${host}-${browserName}-failure.png`), fullPage: true }).catch(() => {})
      }
      if (stage === 'BROWSER_START') {
        record.launchDiagnostic = String(error.message).split(password).join('[redacted]').split(username).join('[redacted]').slice(0, 2000)
      }
    } finally {
      if (browser) await browser.close().catch(() => {})
      await writeFile(path.join(output, 'browser-results.json'), JSON.stringify(results, null, 2), { mode: 0o600 })
    }
  }
}
if (results.some(result => result.status !== 'READ_ONLY_GUI_BASELINE_PASS')) process.exitCode = 1
