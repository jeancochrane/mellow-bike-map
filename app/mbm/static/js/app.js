import UserLocations from './userlocations.js'
import autocomplete from './autocomplete.js'
import Geolocation from './geolocation.js'
import { getUserPreferences, saveUserPreferences } from './storage.js'
// The App class holds top level state and map related methods that other modules
// need to call, for example to update the position of markers.
export default class App {
  constructor(routeListUrl, routeUrl, fromAddress = '', toAddress = '') {
    this.routeListUrl = routeListUrl
    this.routeUrl = routeUrl
    this.fromAddress = fromAddress
    this.toAddress = toAddress

    // The layer that displays the route between the source and target locations
    this.directionsRouteLayer = null

    // The layer that displays the calm routes on the map: "off-street bike paths", "mellow streets", and "main streets, often with bike lanes"
    this.calmRoutesLayer = null
    this.calmRoutesData = null

    this.markers = { 'source': null, 'target': null }

    this.routeTypes = {
      'path': {
        color: '#e17fa8',
        description: 'Off-street bike paths (very calm)',
        visible: true
      },
      'street': {
        color: '#77b7a2',
        description: 'Mellow streets (calm)',
        visible: true
      },
      'route': {
        color: '#e18a7e',
        description: 'Main streets, often with bike lanes (less calm)',
        visible: true
      }
    }

    // Start the app once the DOM is ready
    document.addEventListener('DOMContentLoaded', this.start.bind(this))
    this.sourceLocation = ''
    this.targetLocation = ''
    this.sourceAddressString = ''
    this.targetAddressString = ''
    this.geocoder = null
    this.directionsFormElements = {
      source: {
        input: null,
        autocomplete: null
      },
      target: {
        input: null,
        autocomplete: null
      }
    }
  }

  start() {
    // Create the leaflet map
    this.map = this.createMap()

    // Store references to DOM elements we'll need
    const $directionsForm = $('#input-elements')
    const sourceInput = document.getElementById('source')

    const targetInput = document.getElementById('target')

    // This uses the same keys as the `markers` object for convenience
    // in the code below
    this.directionsFormElements = {
      source: {
        input: sourceInput,
        autocomplete: null
      },
      target: {
        input: targetInput,
        autocomplete: null
      }
    }

    this.$routeEstimate = $('#route-estimate')

    // Setup interactive tooltip elements (via jQuery UI)
    $('[data-toggle="tooltip"]').tooltip()

    this.gpsLocationString = 'My position'

    const isMobileScreen = $(window).outerWidth() <= 768

    // Make sure the map always fits the full height of the screen
    $(window).resize(() => {
      var windowHeight = $(window).innerHeight()
      var offsetTop = $('.navbar')[0].offsetHeight
      // Add controls to the top offset on mobile screens, where they merge
      // with the navbar
      if (isMobileScreen) { offsetTop += $('#controls-container')[0].offsetHeight }
      var mapHeight = windowHeight - offsetTop
      $('#map').css('height', mapHeight)
    }).resize()

    // Recalculate map size when controls are toggled
    $directionsForm.on('shown.bs.collapse hidden.bs.collapse', function (e) {
      $(window).resize()
    })

    this.createLegend().addTo(this.map)

    // Allow users to name and save their own locations by double clicking on the map
    this.userLocationsCheckbox = document.getElementById('enable-user-locations')
    this.handleLocationsCheckboxChange = (event) => {
      this.preferences.userLocationsEnabled = event.target.checked
      saveUserPreferences(this.preferences)

      if (event.target.checked && !this.userLocations) {
        this.userLocations = new UserLocations(this)
      } else {
        this.userLocations.unmount()
        this.userLocations = null
      }
    }
    this.userLocationsCheckbox.addEventListener('change', this.handleLocationsCheckboxChange)

    this.preferences = getUserPreferences()
    if (this.preferences.userLocationsEnabled) {
      this.userLocationsCheckbox.checked = true
      this.userLocationsCheckbox.dispatchEvent(new Event('change'))
    }

    // Load the routes layer (first call hits backend, subsequent reloads reuse cache)
    this.loadCalmRoutes()

    // Define behavior for the search button
    $directionsForm.submit(this.search.bind(this))

    // Define behavior for the "Reset search" button
    $('#reset-search').click(this.reset.bind(this))

    const isHidden = (elem) => { return $(elem).data('state') === 'hidden' }

    const toggleControlText = (elem, showText, hideText) => {
      let innerHTML
      let state
      if (isHidden(elem)) {
        innerHTML = `&and; ${hideText}`
        state = 'shown'
      } else {
        innerHTML = `&or; ${showText}`
        state = 'hidden'
      }
      $(elem).html(innerHTML)
      $(elem).data('state', state)
    }

    const toggleControlElement = (elem, controlSelector) => {
      if (isHidden(elem)) {
        $(controlSelector).show()
      } else {
        $(controlSelector).hide()
      }
    }

    this.$hideSearch = $('#hide')
    // Toggle text on Show/Hide button
    this.$hideSearch.click(function (e) {
      $(window).resize()
      toggleControlText(this, 'Search for a route', 'Hide search box')
    })

    this.$hideLegend = $('#hide-legend')
    this.$hideLegend.click(function (e) {
      toggleControlElement(this, '.hideable-legend')
      toggleControlText(this, 'Show legend', 'Hide legend')
    })

    // Show the search box by default on desktop
    if (!isMobileScreen) { this.$hideSearch.click() }

    // Watch the user's location and update the map as it changes
    this.geolocation = new Geolocation(this)

    // Set up google autocomplete for the source/target search inputs
    for (const [name, { input }] of Object.entries(this.directionsFormElements)) {
      this.directionsFormElements[name]['autocomplete'] = autocomplete.initAutocomplete(input, name, this)
    }

    // Add "My position" as an option to the autocomplete
    autocomplete.addCustomOption(this, this.gpsLocationString, (markerName) => {
      const latlng = this.geolocation.marker.getLatLng()
      this.setSourceOrTargetLocation(markerName, latlng.lat, latlng.lng, this.gpsLocationString)
    })

    this.applyInitialQueryParams(window.location.search)
  }

  async applyInitialQueryParams(searchString = '') {
    const urlParams = new URLSearchParams(searchString)
    const sourceAddressParam = urlParams.get('sourceAddress')
    const targetAddressParam = urlParams.get('targetAddress')
    const sourceCoordsParam = urlParams.get('sourceCoordinates')
    const targetCoordsParam = urlParams.get('targetCoordinates')
    const sourceCoordsFromUrl = this.parseCoordinateParam(sourceCoordsParam)
    const targetCoordsFromUrl = this.parseCoordinateParam(targetCoordsParam)
    const sourceAddress = sourceAddressParam || this.fromAddress
    const targetAddress = targetAddressParam || this.toAddress

    if (sourceAddressParam) {
      this.sourceAddressString = sourceAddressParam
      this.prefillAddressInput('source', sourceAddressParam)
    }
    if (targetAddressParam) {
      this.targetAddressString = targetAddressParam
      this.prefillAddressInput('target', targetAddressParam)
    }

    if (sourceCoordsFromUrl) {
      const sourceHasAddress = Boolean(sourceAddress)
      const sourceDisplay = sourceHasAddress ? sourceAddress : sourceCoordsParam
      this.setSourceLocation(sourceCoordsFromUrl.lat, sourceCoordsFromUrl.lng, sourceDisplay)
    }
    if (targetCoordsFromUrl) {
      const targetHasAddress = Boolean(targetAddress)
      const targetDisplay = targetHasAddress ? targetAddress : targetCoordsParam
      this.setTargetLocation(targetCoordsFromUrl.lat, targetCoordsFromUrl.lng, targetDisplay)
    }

    const submitIfReady = () => {
      if (this.sourceLocation && this.targetLocation) {
        this.submitSearchForm()
        return true
      }
      return false
    }

    const geocodeJobs = []
    const addJob = (kind, address, setter) => {
      geocodeJobs.push(
        this.geocodeAddress(address).then(({ lat, lng }) => setter(lat, lng)).catch((status) => {
          console.error(`Geocode failed for ${kind} address:`, status)
          alert(`Could not find the ${kind} address: ` + address)
          throw status
        })
      )
    }

    if (!sourceCoordsFromUrl && sourceAddress) {
      addJob('start', sourceAddress, (lat, lng) => this.setSourceLocation(lat, lng, sourceAddress))
    }
    if (!targetCoordsFromUrl && targetAddress) {
      addJob('destination', targetAddress, (lat, lng) => this.setTargetLocation(lat, lng, targetAddress))
    }

    if (geocodeJobs.length) {
      try {
        await Promise.all(geocodeJobs)
      } catch (err) {
        return false
      }
    }

    submitIfReady()
    return true
  }

  submitSearchForm() {
    $('#input-elements').submit()
  }

  geocodeAddress(address) {
    if (!this.geocoder) {
      this.geocoder = new google.maps.Geocoder()
    }
    return new Promise((resolve, reject) => {
      this.geocoder.geocode({ address }, (results, status) => {
        if (status === 'OK' && results[0]) {
          const location = results[0].geometry.location
          resolve({ lat: location.lat(), lng: location.lng() })
        } else {
          reject(status)
        }
      })
    })
  }

  // Fetch (once) and render the annotated routes layer, caching the data after the initial request
  loadCalmRoutes() {
    if (this.calmRoutesData) {
      this.renderCalmRoutesLayer(this.calmRoutesData)
      return
    }

    // Start spinner while we retrieve initial route map
    this.map.spin(true)
    $.getJSON(this.routeListUrl).done((data) => {
      this.calmRoutesData = data
      this.renderCalmRoutesLayer(data)
    }).fail(function (jqxhr, textStatus, error) {
      console.log(textStatus + ': ' + error)
    }).always(() => {
      this.map.spin(false)
    })
  }

  renderCalmRoutesLayer(data) {
    if (this.calmRoutesLayer) {
      this.map.removeLayer(this.calmRoutesLayer)
      this.calmRoutesLayer = null
    }

    this.calmRoutesLayer = L.geoJSON(data, {
      style: (feature) => {
        return { color: this.getLineColor(feature.properties.type), opacity: 0.6 }
      },
      interactive: false,
      filter: (feature) => {
        const routeType = this.routeTypes[feature.properties.type]
        return routeType ? routeType.visible === true : false
      }
    }).addTo(this.map)
  }

  // Create a legend
  createLegend() {
    const legend = L.control({ position: 'bottomright' })
    legend.onAdd = (map) => {
      let div = L.DomUtil.create('div', 'info legend hideable-legend')
      const routeEntries = Object.entries(this.routeTypes)
      for (const [type, { color, description, visible }] of routeEntries) {
        const lineColor = color || '#7ea4e1'
        
        // Create a container for each legend item
        const item = L.DomUtil.create('div', 'legend-item', div)
        item.setAttribute('data-route-type', type)
        if (!visible) {
          item.classList.add('legend-item-inactive')
        }
        
        // Create the color box
        const colorBox = L.DomUtil.create('i', '', item)
        colorBox.style.background = lineColor
        
        // Create the text label
        const label = L.DomUtil.create('span', '', item)
        label.textContent = description
        
        // Add click handler to container to toggle the visibility of the route type
        L.DomEvent.on(item, 'click', (e) => {
          L.DomEvent.stopPropagation(e)
          this.toggleCalmRouteTypeVisibility(type)
        })
      }
      
      // Prevent map interactions when clicking on legend
      L.DomEvent.disableClickPropagation(div)
      
      return div
    }
    return legend
  }

  getLineColor(type) {
    const routeType = this.routeTypes[type]
    return routeType ? routeType.color : '#7ea4e1'
  }

  // Toggle the visibility of a route type
  toggleCalmRouteTypeVisibility(type) {
    const routeType = this.routeTypes[type]
    if (!routeType) { return }
    routeType.visible = !routeType.visible
    
    // Update the legend item appearance
    const legendItem = document.querySelector(`.legend-item[data-route-type="${type}"]`)
    if (legendItem) {
      if (routeType.visible) {
        legendItem.classList.remove('legend-item-inactive')
      } else {
        legendItem.classList.add('legend-item-inactive')
      }
    }
    
    // Reload the routes layer with the new filter
    this.reloadCalmRoutes()
  }

  // Reload all routes with current filters
  reloadCalmRoutes() {
    if (this.calmRoutesLayer) {
      this.map.removeLayer(this.calmRoutesLayer)
      this.calmRoutesLayer = null
    }
    this.loadCalmRoutes()
  }

  parseCoordinateParam(value) {
    if (!value) { return null }
    const parts = value.split(',')
    if (parts.length !== 2) { return null }
    const lat = parseFloat(parts[0])
    const lng = parseFloat(parts[1])
    if (Number.isNaN(lat) || Number.isNaN(lng)) { return null }
    return { lat, lng }
  }

  prefillAddressInput(name, value) {
    const element = this.directionsFormElements[name]
    if (element && element.input) {
      element.input.value = value
    }
  }

  // Try to parse the value of the input field as a coordinate string and set the location if successful
  applyCoordinatesInput(markerName) {
    const element = this.directionsFormElements && this.directionsFormElements[markerName]
    if (!element || !element.input) { return }
    const rawValue = (element.input.value || '').trim()
    if (!rawValue) { return }
    const coords = this.parseCoordinateParam(rawValue)
    if (!coords) { return }
    this.setSourceOrTargetLocation(markerName, coords.lat, coords.lng, rawValue)
  }

  escapeHtml(value = '') {
    const htmlEscapes = {
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#39;'
    }
    return value.replace(/[&<>"']/g, (char) => htmlEscapes[char])
  }

  updateUrlWithParams(params) {
    const basePath = '/'
    const query = params.toString()
    const newUrl = query ? `${basePath}?${query}` : basePath
    window.history.pushState({}, '', newUrl)
  }

  inputUsesCoordinates(markerName) {
    const element = this.directionsFormElements && this.directionsFormElements[markerName]
    if (!element || !element.input) { return false }
    const rawValue = (element.input.value || '').trim()
    if (!rawValue) { return false }
    return Boolean(this.parseCoordinateParam(rawValue))
  }

  clearRouteQueryParams() {
    const params = new URLSearchParams(window.location.search)
    params.delete('sourceAddress')
    params.delete('targetAddress')
    params.delete('sourceCoordinates')
    params.delete('targetCoordinates')
    this.updateUrlWithParams(params)
  }

  setRouteQueryParams(fromAddr, toAddr, sourceCoords, targetCoords) {
    const params = new URLSearchParams(window.location.search)
    if (fromAddr) {
      params.set('sourceAddress', fromAddr)
    } else {
      params.delete('sourceAddress')
    }
    if (toAddr) {
      params.set('targetAddress', toAddr)
    } else {
      params.delete('targetAddress')
    }
    if (sourceCoords) {
      params.set('sourceCoordinates', sourceCoords)
    } else {
      params.delete('sourceCoordinates')
    }
    if (targetCoords) {
      params.set('targetCoordinates', targetCoords)
    } else {
      params.delete('targetCoordinates')
    }
    this.updateUrlWithParams(params)
  }

  // Clear the form and remove plotted directions from the map
  // Inputs are automatically reset because the button that triggers this has `type="reset"`
  reset() {
    if (this.directionsRouteLayer) { this.map.removeLayer(this.directionsRouteLayer) }
    if (this.markers['source']) { this.map.removeLayer(this.markers['source']) }
    if (this.markers['target']) { this.map.removeLayer(this.markers['target']) }
    this.calmRoutesLayer.setStyle({ opacity: 0.6 })
    this.hideRouteEstimate()
    this.sourceAddressString = ''
    this.targetAddressString = ''
    this.clearRouteQueryParams()
  }

  // Set up the base leaflet map and styles
  createMap() {
    const map = L.map('map')

    const googleStyles = [
      {
        stylers: [
          { saturation: -100 },
          { lightness: 40 }
        ]
      },
      {
        featureType: 'poi',
        elementType: 'labels',
        stylers: [{ visibility: 'off' }]
      },
      {
        featureType: 'transit',
        elementType: 'labels',
        stylers: [{ visibility: 'off' }]
      },
      {
        featureType: 'administrative.neighborhood',
        elementType: 'labels',
        stylers: [{ visibility: 'off' }]
      },
      {
        featureType: 'road.highway',
        elementType: 'labels',
        stylers: [{ visibility: 'off' }]
      },
    ]

    // Load basemap
    const streets = new L.Google('ROADMAP', { mapOptions: { styles: googleStyles } })
    map.addLayer(streets).setView([41.87, -87.62], 11)

    map.attributionControl.setPrefix('')
    map.attributionControl.addAttribution(
      '<a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a>'
    )

    return map
  }

  // Search for a chill route between the two locations selected in the
  // form, then display it on the map
  search(e) {
    e.preventDefault()
    this.applyCoordinatesInput('source')
    this.applyCoordinatesInput('target')
    const source = this.sourceLocation
    const target = this.targetLocation
    const enableV2 = $('#enable-v2').is(':checked')
    if (source === '') {
      alert('Source is required for search')
    } else if (target == '') {
      alert('Target is required for search')
    } else {
      const fromAddr = this.inputUsesCoordinates('source') ? null : this.sourceAddressString
      const toAddr = this.inputUsesCoordinates('target') ? null : this.targetAddressString
      const sourceCoords = this.sourceLocation
      const targetCoords = this.targetLocation

      this.setRouteQueryParams(fromAddr, toAddr, sourceCoords, targetCoords)

      this.map.spin(true)
      $.getJSON(this.routeUrl + '?' + $.param({ source, target, enable_v2: enableV2 })).done((data) => {
        if (this.directionsRouteLayer) {
          this.map.removeLayer(this.directionsRouteLayer)
        }
        this.directionsRouteLayer = L.geoJSON(data.route, {
          style: (feature) => {
            return { weight: 5, color: this.getLineColor(feature.properties.type) }
          },
          onEachFeature: function (feature, layer) {
            layer.bindPopup(
              `<strong>Name:</strong> ${feature.properties.name}<br>` +
              `<strong>Type:</strong> ${feature.properties.type ? feature.properties.type : 'non-mellow street'}`
            )
          }
        }).addTo(this.map)
        // Lower opacity on non-route street colors
        this.calmRoutesLayer.setStyle({ opacity: 0.3 })
        this.map.fitBounds(this.directionsRouteLayer.getBounds())
        this.showRouteEstimate(
          data.route.properties.distance,
          data.route.properties.time,
          data.route.properties.major_streets
        )
      }).fail((jqxhr, textStatus, error) => {
        const err = textStatus + ': ' + error
        alert('Request failed: ' + err)
      }).always(() => {
        this.map.spin(false)
      })
    }
  }

  // Create a marker or move an existing one to a new location. If addressString
  // is supplied, and markerName is "source" or "target", also update the associated
  // <input> to show addressString.
  setMarkerLocation(markerName, lat, lng, addressString = '') {
    // Create the marker if it doesn't exist
    if (!this.markers[markerName]) {
      this.addMarker(markerName, L.marker([lat, lng]))
    } else {
      // Move it to the new location if it does
      this.markers[markerName].setLatLng({
        lat: lat,
        lng: lng
      })
    }

    if (this.directionsFormElements[markerName]) {
      const { input } = this.directionsFormElements[markerName]

      if (addressString) {
        const escapedAddress = this.escapeHtml(addressString)
        // Update the marker's popup with escaped HTML
        this.markers[markerName].unbindPopup().bindPopup(escapedAddress)
        // Update the user-facing text input field
        input.value = addressString
      }

      this.map.setView([lat, lng])

      return this.markers[markerName]
    }
  }

  zoomToLocation(lat, lng) {
    this.map.setView([lat, lng], 14)
  }

  serializeLocation(lat, lng) {
    return `${lat},${lng}`
  }

  setSourceOrTargetLocation(markerName, lat, lng, addressString) {
    if (markerName === "source") {
      this.setSourceLocation(lat, lng, addressString)
    } else if (markerName === "target") {
      this.setTargetLocation(lat, lng, addressString)
    }
  }

  setSourceLocation(lat, lng, addressString) {
    this.sourceLocation = this.serializeLocation(lat, lng)
    this.sourceAddressString = addressString
    this.setMarkerLocation('source', lat, lng, addressString)
  }

  setTargetLocation(lat, lng, addressString) {
    this.targetLocation = this.serializeLocation(lat, lng)
    this.targetAddressString = addressString
    this.setMarkerLocation('target', lat, lng, addressString)
  }

  // Remove a marker from the map and our list of markers
  removeMarker(name) {
    this.map.removeLayer(this.markers[name])
    delete this.markers[name]
  }

  // Add a marker to the map and our list of markers
  addMarker(name, marker) {
    marker.addTo(this.map)
    this.markers[name] = marker
  }

  showRouteEstimate(distance, time, majorStreets = []) {
    const viaText = this.formatViaText(majorStreets)
    const summary = viaText ? `<strong>${time}</strong> (${distance}) ${viaText}` : `<strong>${time}</strong> (${distance})`
    this.$routeEstimate.html(summary)
    this.$routeEstimate.show()
    this.$hideSearch.addClass('mt-1')
    this.$hideLegend.addClass('mt-1')
  }

  formatViaText(streets = []) {
    const names = streets.slice(0, 3).filter(name => !!name)
    if (names.length === 0) {
      return ''
    }
    if (names.length === 1) {
      return `via ${names[0]}`
    }
    if (names.length === 2) {
      return `via ${names[0]} and ${names[1]}`
    }
    const leading = names.slice(0, -1).join(', ')
    const last = names[names.length - 1]
    return `via ${leading}, and ${last}`
  }

  hideRouteEstimate() {
    this.$routeEstimate.hide()
    this.$routeEstimate.html('')
    this.$hideSearch.removeClass('mt-1')
    this.$hideLegend.removeClass('mt-1')
  }
}
