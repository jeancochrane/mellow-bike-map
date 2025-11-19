import test from 'node:test'
import assert from 'node:assert/strict'
import App from '../mbm/static/js/app.js'

global.document = {
  addEventListener: () => {}
}

const noop = () => {}

const createApp = ({ fromAddress = '', toAddress = '' } = {}) => {
  const app = new App('/routes', '/route', fromAddress, toAddress)
  let submitCount = 0

  app.submitSearchForm = () => { submitCount += 1 }
  app.setSourceLocation = (lat, lng, address) => {
    app.sourceLocation = `${lat},${lng}`
    app.sourceAddressString = address
  }
  app.setTargetLocation = (lat, lng, address) => {
    app.targetLocation = `${lat},${lng}`
    app.targetAddressString = address
  }

  return {
    app,
    getSubmitCount: () => submitCount
  }
}

const mockAjax = () => {
  const chain = {
    done: noop,
    fail: noop,
    always: noop
  }
  chain.done = function () { return this }
  chain.fail = function () { return this }
  chain.always = function (cb) { if (cb) { cb() } return this }
  return chain
}

test.beforeEach(() => {
  global.alert = () => {}
  global.window = {
    location: { search: '' },
    history: { pushState: noop }
  }
  const dollar = (selector) => {
    if (selector === '#enable-v2') {
      return { is: () => false }
    }
    if (selector === '#input-elements') {
      return { submit: noop }
    }
    return {
      is: () => false
    }
  }
  dollar.getJSON = () => mockAjax()
  dollar.param = (obj) => new URLSearchParams(obj).toString()
  global.$ = dollar
})

test('applies provided coordinates and submits immediately', async () => {
  const { app, getSubmitCount } = createApp({ fromAddress: 'Start', toAddress: 'End' })

  await app.applyInitialQueryParams('?sourceCoordinates=1,2&targetCoordinates=3,4')

  assert.equal(app.sourceLocation, '1,2')
  assert.equal(app.targetLocation, '3,4')
  assert.equal(app.sourceAddressString, 'Start')
  assert.equal(app.targetAddressString, 'End')
  assert.equal(getSubmitCount(), 1)
})

test('geocodes a missing destination before submitting', async () => {
  const { app, getSubmitCount } = createApp({ fromAddress: 'Start', toAddress: 'End' })
  const geocodeCalls = []
  app.geocodeAddress = (address) => {
    geocodeCalls.push(address)
    if (address === 'End') {
      return Promise.resolve({ lat: 41.9, lng: -87.7 })
    }
    return Promise.resolve({ lat: 41.8, lng: -87.6 })
  }

  await app.applyInitialQueryParams('?sourceCoordinates=1,2')

  assert.deepEqual(geocodeCalls, ['End'])
  assert.equal(app.targetLocation, '41.9,-87.7')
  assert.equal(getSubmitCount(), 1)
})

test('alerts if only one of source or target location is provided in query params but not the other', async () => {
  const { app } = createApp({ toAddress: 'End' })
  let alertMessage = ''
  global.alert = (message) => { alertMessage = message }

  await app.applyInitialQueryParams('?targetCoordinates=3,4')

  assert.match(alertMessage, /start and end locations/)
})

test('shows coordinate strings when no address is provided', async () => {
  const { app, getSubmitCount } = createApp()

  await app.applyInitialQueryParams('?sourceCoordinates=1.25,2.5&targetCoordinates=3.75,4.5')

  assert.equal(app.sourceAddressString, '1.25,2.5')
  assert.equal(app.targetAddressString, '3.75,4.5')
  assert.equal(app.sourceLocation, '1.25,2.5')
  assert.equal(app.targetLocation, '3.75,4.5')
  assert.equal(getSubmitCount(), 1)
})

test('skips submission when geocoding fails', async () => {
  const { app, getSubmitCount } = createApp({ fromAddress: 'Start', toAddress: 'End' })
  const alerts = []
  global.alert = (message) => { alerts.push(message) }
  app.geocodeAddress = (address) => {
    if (address === 'End') {
      return Promise.reject('ZERO_RESULTS')
    }
    return Promise.resolve({ lat: 1, lng: 2 })
  }

  const result = await app.applyInitialQueryParams('')

  assert.equal(result, false)
  assert.equal(getSubmitCount(), 0)
  assert.ok(alerts.some((msg) => msg.includes('destination')))
})

test('does not auto-submit when query params are empty', async () => {
  const { app, getSubmitCount } = createApp()

  await app.applyInitialQueryParams('')

  assert.equal(getSubmitCount(), 0)
})

test('search populates query params after manual submission', async () => {
  const historyCalls = []
  global.window.history.pushState = (_state, _title, url) => {
    historyCalls.push(url)
    const queryIndex = url.indexOf('?')
    global.window.location.search = queryIndex >= 0 ? url.slice(queryIndex) : ''
  }

  const { app } = createApp()
  app.map = {
    spin: noop,
    removeLayer: noop,
    fitBounds: noop
  }
  app.allRoutesLayer = { setStyle: noop }
  app.showRouteEstimate = noop
  app.sourceLocation = '1,2'
  app.targetLocation = '3,4'
  app.sourceAddressString = 'Start Address'
  app.targetAddressString = 'End Address'

  app.search({ preventDefault: noop })

  assert.ok(historyCalls.length > 0, 'history.pushState should be called')
  const lastUrl = historyCalls.at(-1)
  const params = new URLSearchParams(lastUrl.split('?')[1] || '')
  assert.equal(params.get('sourceAddress'), 'Start Address')
  assert.equal(params.get('targetAddress'), 'End Address')
  assert.equal(params.get('sourceCoordinates'), '1,2')
  assert.equal(params.get('targetCoordinates'), '3,4')
})

test('manual search preserves unrelated query parameters', async () => {
  const historyCalls = []
  global.window.location.search = '?utm_source=chatgpt.com'
  global.window.history.pushState = (_state, _title, url) => {
    historyCalls.push(url)
    const queryIndex = url.indexOf('?')
    global.window.location.search = queryIndex >= 0 ? url.slice(queryIndex) : ''
  }

  const { app } = createApp()
  app.map = {
    spin: noop,
    removeLayer: noop,
    fitBounds: noop
  }
  app.allRoutesLayer = { setStyle: noop }
  app.showRouteEstimate = noop
  app.sourceLocation = '10,20'
  app.targetLocation = '30,40'
  app.sourceAddressString = 'Start'
  app.targetAddressString = 'End'

  app.search({ preventDefault: noop })

  const lastUrl = historyCalls.at(-1)
  const params = new URLSearchParams(lastUrl.split('?')[1] || '')
  assert.equal(params.get('sourceAddress'), 'Start')
  assert.equal(params.get('targetAddress'), 'End')
  assert.equal(params.get('sourceCoordinates'), '10,20')
  assert.equal(params.get('targetCoordinates'), '30,40')
  assert.equal(params.get('utm_source'), 'chatgpt.com')
})