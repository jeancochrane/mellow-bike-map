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

test('prefills just the source address and not the target address without auto-submitting', async () => {
  const { app, getSubmitCount } = createApp()
  const geocodeCalls = []
  let alertCount = 0
  global.alert = () => { alertCount += 1 }
  app.geocodeAddress = (address) => {
    geocodeCalls.push(address)
    return Promise.resolve({ lat: 10, lng: 20 })
  }

  await app.applyInitialQueryParams('?sourceAddress=Solo Start')

  assert.deepEqual(geocodeCalls, ['Solo Start'])
  assert.equal(app.sourceLocation, '10,20')
  assert.equal(app.sourceAddressString, 'Solo Start')
  assert.equal(getSubmitCount(), 0)
  assert.equal(alertCount, 0)
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

test('does not geocode when coordinates provided in query params', async () => {
  const { app } = createApp()
  let geocodeCount = 0
  app.geocodeAddress = () => {
    geocodeCount += 1
    return Promise.resolve({ lat: 1, lng: 2 })
  }

  await app.applyInitialQueryParams('?sourceCoordinates=41.9,-87.6&targetCoordinates=42.0,-87.7')

  assert.equal(geocodeCount, 0)
  assert.equal(app.sourceLocation, '41.9,-87.6')
  assert.equal(app.targetLocation, '42,-87.7')
})

test('skips submission when geocoding fails', async () => {
  const { app, getSubmitCount } = createApp({ fromAddress: 'Start', toAddress: 'End' })
  const alerts = []
  global.alert = (message) => { alerts.push(message) }
  const consoleErrors = []
  const originalConsoleError = console.error
  console.error = (...args) => { consoleErrors.push(args) }
  app.geocodeAddress = (address) => {
    if (address === 'End') {
      return Promise.reject('ZERO_RESULTS')
    }
    return Promise.resolve({ lat: 1, lng: 2 })
  }

  const result = await app.applyInitialQueryParams('')

  console.error = originalConsoleError // Restore original console.error
  assert.equal(result, false)
  assert.equal(getSubmitCount(), 0)
  assert.ok(alerts.some((msg) => msg.includes('destination')))
  assert.equal(consoleErrors.length, 1)
  assert.equal(consoleErrors[0][0], 'Geocode failed for destination address:')
  assert.equal(consoleErrors[0][1], 'ZERO_RESULTS')
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
  global.window.location.search = '?utm_source=duckduckgo.com'
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
  assert.equal(params.get('utm_source'), 'duckduckgo.com')
})

test('manual search accepts coordinate input strings', () => {
  const { app } = createApp()
  const getJSONUrls = []
  const originalGetJSON = $.getJSON
  $.getJSON = (url) => {
    getJSONUrls.push(url)
    return mockAjax()
  }
  const historyCalls = []
  global.window.history.pushState = (_state, _title, url) => {
    historyCalls.push(url)
    const queryIndex = url.indexOf('?')
    global.window.location.search = queryIndex >= 0 ? url.slice(queryIndex) : ''
  }

  app.map = {
    spin: noop,
    removeLayer: noop,
    fitBounds: noop
  }
  app.allRoutesLayer = { setStyle: noop }
  app.showRouteEstimate = noop
  app.directionsFormElements.source.input = { value: '41.8,-87.6' }
  app.directionsFormElements.target.input = { value: '41.9,-87.7' }

  app.sourceLocation = ''
  app.targetLocation = ''

  app.search({ preventDefault: noop })

  $.getJSON = originalGetJSON

  assert.equal(app.sourceLocation, '41.8,-87.6')
  assert.equal(app.targetLocation, '41.9,-87.7')
  assert.equal(getJSONUrls.length, 1)
  const params = new URLSearchParams(getJSONUrls[0].split('?')[1])
  assert.equal(params.get('source'), '41.8,-87.6')
  assert.equal(params.get('target'), '41.9,-87.7')
  const lastUrl = historyCalls.at(-1)
  const locationParams = new URLSearchParams(lastUrl.split('?')[1] || '')
  assert.equal(locationParams.get('sourceAddress'), null)
  assert.equal(locationParams.get('targetAddress'), null)
  assert.equal(locationParams.get('sourceCoordinates'), '41.8,-87.6')
  assert.equal(locationParams.get('targetCoordinates'), '41.9,-87.7')
})

test('manual coordinate search removes existing address params', () => {
  const historyCalls = []
  global.window.location.search = '?sourceAddress=OldStart&targetAddress=OldEnd&utm_source=duckduckgo.com'
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
  app.directionsFormElements.source.input = { value: '42.0,-87.7' }
  app.directionsFormElements.target.input = { value: '42.1,-87.8' }
  app.sourceLocation = ''
  app.targetLocation = ''

  app.search({ preventDefault: noop })

  const lastUrl = historyCalls.at(-1)
  const params = new URLSearchParams(lastUrl.split('?')[1] || '')
  assert.equal(params.get('sourceAddress'), null)
  assert.equal(params.get('targetAddress'), null)
  assert.equal(params.get('sourceCoordinates'), '42,-87.7')
  assert.equal(params.get('targetCoordinates'), '42.1,-87.8')
  assert.equal(params.get('utm_source'), 'duckduckgo.com')
})
