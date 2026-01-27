import UserLocations from './userlocations.js'
import autocomplete from './autocomplete.js'
import Geolocation from './geolocation.js'
import { getUserLocations, getUserPreferences, saveUserPreferences } from './storage.js'
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
    this.routeData = null
    this.highlightLayer = null
    this.highlightGlowLayer = null
    this.parksLayer = null  // For debug mode: shows park boundaries

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
    
    // Track if directions are explicitly shown on mobile (user clicked "Turn by turn" button)
    this.mobileDirectionsShown = false
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

    // Prevent settings dropdown from closing when clicking on checkboxes
    $('#settings-dropdown-menu').on('click', function(e) {
      e.stopPropagation();
    });

    this.gpsLocationString = 'My position'

    const getIsMobileScreen = () => $(window).outerWidth() <= 768
    let previousIsMobileScreen = null

    this.$hideSearch = $('#hide')
    this.$hideLegend = $('#hide-legend')

    const setSearchToggleState = (state) => {
      if (!this.$hideSearch.length) { return }
      const label = state === 'hidden' ? '&or; Search for a route' : '&and; Hide search box'
      this.$hideSearch.html(label)
      this.$hideSearch.data('state', state)
      this.$hideSearch.attr('aria-expanded', state === 'shown')
    }

    const setLegendToggleState = (state) => {
      if (!this.$hideLegend.length) { return }
      const label = state === 'hidden' ? '&or; Show legend' : '&and; Hide legend'
      this.$hideLegend.html(label)
      this.$hideLegend.data('state', state)
      this.$hideLegend.attr('aria-expanded', state === 'shown')
    }

    const getNextState = ($button) => {
      return $button.data('state') === 'hidden' ? 'shown' : 'hidden'
    }

    const adjustControlsForViewport = (isMobile) => {
      if (isMobile) {
        $('#input-elements').collapse('hide')
        setSearchToggleState('hidden')
      } else {
        $('#input-elements').collapse('show')
        setSearchToggleState('shown')
        $('.hideable-legend').show()
        setLegendToggleState('shown')
      }
    }

    const handleResize = () => {
      const isMobile = getIsMobileScreen()
      if (previousIsMobileScreen === null || previousIsMobileScreen !== isMobile) {
        adjustControlsForViewport(isMobile)
        previousIsMobileScreen = isMobile
      }
      var windowHeight = $(window).innerHeight()
      var offsetTop = $('.navbar')[0].offsetHeight
      // Add controls to the top offset on mobile screens, where they merge
      // with the navbar
      if (isMobile) { offsetTop += $('#controls-container')[0].offsetHeight }
      var mapHeight = windowHeight - offsetTop
      $('#map').css('height', mapHeight)
    }

    if (this.$hideSearch.length) {
      this.$hideSearch.click(() => {
        const nextState = getNextState(this.$hideSearch)
        setSearchToggleState(nextState)
        if (nextState === 'hidden') {
          $('#input-elements').collapse('hide')
        } else {
          $('#input-elements').collapse('show')
        }
        handleResize()
      })
    }

    if (this.$hideLegend.length) {
      this.$hideLegend.click(() => {
        const nextState = getNextState(this.$hideLegend)
        setLegendToggleState(nextState)
        if (nextState === 'hidden') {
          $('.hideable-legend').hide()
        } else {
          $('.hideable-legend').show()
        }
      })
    }

    // Make sure the map always fits the full height of the screen
    $(window).resize(handleResize)
    handleResize()

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

    // ===== DEBUG MODE: Load park boundaries =====
    // Check if debug mode is enabled via URL parameter
    const urlParams = new URLSearchParams(window.location.search)
    const debugMode = urlParams.get('debug') === 'true'
    if (debugMode) {
      this.loadParkBoundaries()
    }
    // ===== END DEBUG MODE =====

    // Define behavior for the search button
    $directionsForm.submit(this.search.bind(this))

    // Define behavior for the "Reset search" button
    $('#reset-search').click(this.reset.bind(this))

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

    // Position directions container based on screen size
    this.positionDirectionsContainer()
    $(window).on('resize', () => {
      this.positionDirectionsContainer()
    })

    // Set up mobile directions show/hide buttons
    const $showDirectionsBtn = $('#show-directions-btn')
    const $hideDirectionsBtn = $('#hide-directions-btn')
    
    if ($showDirectionsBtn.length) {
      $showDirectionsBtn.on('click', () => {
        const $directionsContainer = $('#mobile-directions-container')
        const isMobileScreen = $(window).outerWidth() <= 768
        if (isMobileScreen) {
          $directionsContainer.show()
          this.mobileDirectionsShown = true
          this.updateMobileDirectionsButtons()
        }
      })
    }
    
    if ($hideDirectionsBtn.length) {
      $hideDirectionsBtn.on('click', () => {
        const $directionsContainer = $('#mobile-directions-container')
        const isMobileScreen = $(window).outerWidth() <= 768
        if (isMobileScreen) {
          $directionsContainer.hide()
          this.mobileDirectionsShown = false
          this.updateMobileDirectionsButtons()
        }
      })
    }
    
    // Set up toggle directions size button
    const $toggleDirectionsSizeBtn = $('#toggle-directions-size-btn')
    if ($toggleDirectionsSizeBtn.length) {
      $toggleDirectionsSizeBtn.on('click', () => {
        const $directionsContainer = $('#mobile-directions-container')
        const isMobileScreen = $(window).outerWidth() <= 768
        if (isMobileScreen) {
          $directionsContainer.toggleClass('expanded')
        }
      })
    }

    // If from/to addresses are provided in the URL path, geocode them and auto-run search
    if (this.fromAddress && this.toAddress) {
      this.geocodeAddressesAndRunSearch(this.fromAddress, this.toAddress)
    } else {
      // Otherwise, check for query parameters
      this.applyInitialQueryParams(window.location.search)
    }
  }

  positionDirectionsContainer() {
    const $directionsContainer = $('#mobile-directions-container')
    const $controlsContainer = $('#controls-container')
    const $mapColumn = $('.col-12.col-md-9')
    const $map = $('#map')
    const $showDirectionsBtn = $('#show-directions-btn')
    const isMobileScreen = $(window).outerWidth() <= 768
    const hasDirections = $directionsContainer.find('#directions-list li').length > 0

    if ($directionsContainer.length === 0) {
      return
    }

    if (isMobileScreen) {
      // On mobile, position directions as an overlay on top of the map
      // Ensure map column has relative positioning for absolute positioning of overlay
      if ($mapColumn.css('position') !== 'relative') {
        $mapColumn.css('position', 'relative')
      }
      // Move directions container to map column if not already there
      if ($directionsContainer.parent()[0] !== $mapColumn[0]) {
        $mapColumn.append($directionsContainer)
      }
      // Move show button to map column if not already there
      if ($showDirectionsBtn.length && $showDirectionsBtn.parent()[0] !== $mapColumn[0]) {
        $mapColumn.append($showDirectionsBtn)
      }
      // On mobile, hide directions unless user explicitly showed them
      if (hasDirections) {
        if (this.mobileDirectionsShown) {
          $directionsContainer.show()
        } else {
          $directionsContainer.hide()
        }
      }
      // Update button visibility
      this.updateMobileDirectionsButtons()
    } else {
      // On desktop, move directions into the sidebar (after the form)
      // Reset map column positioning
      $mapColumn.css('position', '')
      if ($directionsContainer.parent()[0] !== $controlsContainer[0]) {
        $controlsContainer.append($directionsContainer)
      }
      // On desktop, ALWAYS show directions if they exist
      if (hasDirections) {
        $directionsContainer.show()
      }
      // Hide the show button on desktop
      $showDirectionsBtn.hide()
      // Reset mobile state when switching to desktop
      this.mobileDirectionsShown = false
    }
  }

  updateMobileDirectionsButtons() {
    const $directionsContainer = $('#mobile-directions-container')
    const $showDirectionsBtn = $('#show-directions-btn')
    const isMobileScreen = $(window).outerWidth() <= 768
    
    if (!isMobileScreen) {
      return
    }
    
    // Show "Turn by turn" button if directions exist but container is hidden
    const hasDirections = $directionsContainer.find('#directions-list li').length > 0
    const isDirectionsVisible = $directionsContainer.is(':visible')
    
    if (hasDirections && !isDirectionsVisible) {
      $showDirectionsBtn.show()
    } else {
      $showDirectionsBtn.hide()
    }
  }

  // When addresses are provided in the URL, we don't have coordinates returned
  // from Google Maps API as we do when selecting addresses from autocomplete,
  // so we need to geocode the addresses by calling the Google Maps API.
  // If the address matches a saved location name, use the saved coordinates instead.
  geocodeAddressesAndRunSearch(fromAddress, toAddress) {
    const geocoder = new google.maps.Geocoder()
    const savedLocations = getUserLocations() || {}
    
    // Helper function to resolve an address (either from saved locations or geocoding)
    const resolveAddress = (address, callback) => {
      // Check if this matches a saved location name
      if (savedLocations[address]) {
        const location = savedLocations[address]
        callback(location.lat, location.lng, address, true)
        return
      }
      
      // Otherwise, geocode it
      geocoder.geocode({ address: address }, (results, status) => {
        if (status === 'OK' && results[0]) {
          const lat = results[0].geometry.location.lat()
          const lng = results[0].geometry.location.lng()
          callback(lat, lng, address, false)
        } else {
          console.error('Geocode failed for address:', address, status)
          alert('Could not find the address: ' + address)
        }
      })
    }
    
    // Resolve the source address
    resolveAddress(fromAddress, (sourceLat, sourceLng, sourceAddress, isSaved) => {
      this.setSourceLocation(sourceLat, sourceLng, sourceAddress)
      
      // Once source is set, resolve the target
      resolveAddress(toAddress, (targetLat, targetLng, targetAddress, isSaved) => {
        this.setTargetLocation(targetLat, targetLng, targetAddress)
        
        // Auto-submit the search
        $('#input-elements').submit()
      })
    })
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

  // ===== DEBUG MODE: Load park boundaries =====
  // Fetch park boundaries from the backend and display them on the map
  // This method is only called when debug mode is enabled (?debug=true)
  loadParkBoundaries() {
    $.getJSON('/api/parks/').done((data) => {
      this.parksLayer = L.geoJSON(data, {
        style: {
          color: '#90EE90',      // Light green border
          weight: 2,
          opacity: 0.7,
          fillColor: '#90EE90',
          fillOpacity: 0.1
        },
        onEachFeature: (feature, layer) => {
          // Add park name as a tooltip
          if (feature.properties.name) {
            layer.bindTooltip(feature.properties.name, {
              permanent: false,
              direction: 'center',
              className: 'park-label'
            })
          }
        }
      }).addTo(this.map)
      console.log('Loaded park boundaries for debug mode')
    }).fail(function (jqxhr, textStatus, error) {
      console.log('Failed to load park boundaries: ' + textStatus + ': ' + error)
    })
  }
  // ===== END DEBUG MODE =====

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

  // Convert a hex color to a lighter shade for highlighting
  getLightColor(hexColor) {
    // Remove the # if present
    const hex = hexColor.replace('#', '')
    
    // Parse RGB values
    const r = parseInt(hex.substring(0, 2), 16)
    const g = parseInt(hex.substring(2, 4), 16)
    const b = parseInt(hex.substring(4, 6), 16)
    
    // Lighten by mixing with white (increase each channel towards 255)
    const lightness = 0.85 // 0.85 = 85% towards white
    const lightR = Math.round(r + (255 - r) * lightness)
    const lightG = Math.round(g + (255 - g) * lightness)
    const lightB = Math.round(b + (255 - b) * lightness)
    
    // Convert back to hex
    return `#${lightR.toString(16).padStart(2, '0')}${lightG.toString(16).padStart(2, '0')}${lightB.toString(16).padStart(2, '0')}`
  }

  // Clear the form and remove plotted directions from the map
  // Inputs are automatically reset because the button that triggers this has `type="reset"`
  reset() {
    if (this.directionsRouteLayer) { this.map.removeLayer(this.directionsRouteLayer) }
    if (this.highlightLayer) { this.map.removeLayer(this.highlightLayer) }
    if (this.highlightGlowLayer) { this.map.removeLayer(this.highlightGlowLayer) }
    if (this.markers['source']) { this.map.removeLayer(this.markers['source']) }
    if (this.markers['target']) { this.map.removeLayer(this.markers['target']) }
    this.calmRoutesLayer.setStyle({ opacity: 0.6 })
    this.hideRouteEstimate()
    this.hideDirections()
    this.sourceAddressString = ''
    this.targetAddressString = ''
    this.routeData = null
    // Clear the URL back to home, but preserve query parameters (like ?debug=true)
    const searchParams = new URLSearchParams(window.location.search)
    const queryString = searchParams.toString()
    window.history.pushState({}, '', '/' + (queryString ? '?' + queryString : ''))
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
      // Update URL with from/to addresses
      // Use the stored address strings, or fall back to the input values
      const fromAddr = this.inputUsesCoordinates('source') ? null : this.sourceAddressString
      const toAddr = this.inputUsesCoordinates('target') ? null : this.targetAddressString
      const sourceCoords = this.sourceLocation
      const targetCoords = this.targetLocation

      // Build query parameters (preserve existing ones and add route params)
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

      // Update URL with query parameters
      this.updateUrlWithParams(params)
      
      this.map.spin(true)
      $.getJSON(this.routeUrl + '?' + $.param({ source, target, enable_v2: enableV2 })).done((data) => {
        // Store the route data for highlighting
        this.routeData = data.route
        
        // Use directions from API if available, otherwise fall back to computing them
        const directions = data.route.directions || []
        this.displayDirections(directions)

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
    if (this.$hideSearch && this.$hideSearch.length) {
      this.$hideSearch.addClass('mt-1')
    }
    if (this.$hideLegend && this.$hideLegend.length) {
      this.$hideLegend.addClass('mt-1')
    }
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
    if (this.$hideSearch && this.$hideSearch.length) {
      this.$hideSearch.removeClass('mt-1')
    }
    if (this.$hideLegend && this.$hideLegend.length) {
      this.$hideLegend.removeClass('mt-1')
    }
  }

  getDirectionIcon(maneuver, color) {
    const icons = {
      'Continue': `<svg class="direction-icon" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M12 4L12 20M12 4L8 8M12 4L16 8" stroke="${color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>`,
      'Turn slightly to the left': `<svg class="direction-icon" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M12 4L12 20M12 4L8 8M12 4L16 8" stroke="${color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" transform="rotate(-15 12 12)"/>
      </svg>`,
      'Turn left': `<svg class="direction-icon" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M19 19V13C19 11.8954 18.1046 11 17 11H7M7 11L11 7M7 11L11 15" stroke="${color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>`,
      'Take a sharp left turn': `<svg class="direction-icon" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M19 19V9C19 7.89543 18.1046 7 17 7H7M7 7L11 3M7 7L11 11" stroke="${color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>`,
      'Turn slightly to the right': `<svg class="direction-icon" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M12 4L12 20M12 4L8 8M12 4L16 8" stroke="${color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" transform="rotate(15 12 12)"/>
      </svg>`,
      'Turn right': `<svg class="direction-icon" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M5 19V13C5 11.8954 5.89543 11 7 11H17M17 11L13 7M17 11L13 15" stroke="${color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>`,
      'Take a sharp right turn': `<svg class="direction-icon" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M5 19V9C5 7.89543 5.89543 7 7 7H17M17 7L13 3M17 7L13 11" stroke="${color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>`,
      'Turn around': `<svg class="direction-icon" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M8 8C8 8 8 4.5 11.5 4.5C15 4.5 16 7 16 10C16 14 12 16 12 16L12 20M12 20L9 17M12 20L15 17" stroke="${color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>`
    }
    return icons[maneuver] || icons['Continue']
  }

  displayDirections(directions) {
    const $directionsList = $('#directions-list')
    const $directionsContainer = $('#mobile-directions-container')
    
    // Clear any existing directions
    $directionsList.empty()
    
    // Check if debug mode is enabled
    const urlParams = new URLSearchParams(window.location.search)
    const debugMode = urlParams.get('debug') === 'true'
    
    // Format debug info from chicago_ways table
    const formatChicagoWaysInfo = (osmData) => {
      if (!osmData) return ''
      
      const parts = []
      parts.push(`OSM ID: ${osmData.osm_id}`)
      if (osmData.tag_id) parts.push(`Tag ID: ${osmData.tag_id}`)
      if (osmData.park_name) parts.push(`Park: ${osmData.park_name}`)
      if (osmData.oneway && osmData.oneway !== 'NO') parts.push(`Oneway: ${osmData.oneway}`)
      if (osmData.rule) parts.push(`Rule: ${osmData.rule}`)
      if (osmData.priority) parts.push(`Priority: ${osmData.priority}`)
      if (osmData.maxspeed_forward) parts.push(`Max Speed Fwd: ${osmData.maxspeed_forward}`)
      if (osmData.maxspeed_backward) parts.push(`Max Speed Back: ${osmData.maxspeed_backward}`)
      if (osmData.length_m) parts.push(`Length: ${osmData.length_m.toFixed(2)}m`)
      
      return parts.join(', ')
    }
    
    // Format debug info from osm_ways table
    const formatOsmWaysInfo = (osmData) => {
      if (!osmData || !osmData.osm_tags) return ''
      
      if (Object.keys(osmData.osm_tags).length > 0) {
        const tagStrings = Object.entries(osmData.osm_tags)
          .map(([key, value]) => `${key}=${value}`)
          .join(', ')
        return `{${tagStrings}}`
      }
      
      return ''
    }
    
    // Format distance from meters to miles or feet
    const formatDistance = (meters) => {
      const metersPerMile = 1609.344
      const metersPerFoot = 0.3048
      const miles = meters / metersPerMile
      
      // Use feet for distances less than 0.09 miles
      if (miles < 0.09) {
        const feet = Math.round(meters / metersPerFoot)
        const unit = feet === 1 ? 'foot' : 'feet'
        return `${feet} ${unit}`
      } else {
        // Round to 1 decimal place (0.x miles)
        const roundedMiles = Math.round(miles * 10) / 10
        const unit = roundedMiles === 1 ? 'mile' : 'miles'
        return `${roundedMiles} ${unit}`
      }
    }
    
    // Get calmness description
    const getCalmnessDescription = (type) => {
      switch (type) {
        case 'path': return 'Off-street bike paths (very calm)'
        case 'street': return 'Mellow streets (calm)'
        case 'route': return 'Main streets, often with bike lanes (less calm)'
        default: return 'Not calm'
      }
    }
    
    // Process and add each direction
    directions.forEach((direction, index) => {
      // Determine maneuver for first direction
      const maneuver = index === 0 ? 'Continue' : direction.maneuver
      
      // Get the color based on the type
      const color = this.getLineColor(direction.type)
      
      // Get the icon with the appropriate color
      const icon = this.getDirectionIcon(maneuver, color)
      
      // Build the direction text
      // Use effectiveName which includes descriptions for unnamed streets (computed in Python)
      const streetName = direction.effectiveName || direction.name || 'an unknown street'
      let directionText = ''
      if (index === 0) {
        directionText = `Head ${direction.cardinal} on ${streetName} for ${formatDistance(direction.distance)}`
      } else {
        directionText = `${direction.maneuver} onto ${streetName} and head ${direction.cardinal} for ${formatDistance(direction.distance)}`
      }
      
      // Add "until you reach your destination" to last direction
      if (index === directions.length - 1) {
        directionText += " until you reach your destination"
      }
      
      // Build the list item with clickable class and color data
      let listItemHtml = `<li class="direction-item" data-direction-index="${index}" data-color="${color}"><span class="direction-icon-wrapper">${icon}</span><span class="direction-text">${directionText}`
      
      // Add debug information if enabled
      if (debugMode) {
        const calmnessInfo = getCalmnessDescription(direction.type)
        
        listItemHtml += `
          <div class="direction-debug-info">
            <div><span class="debug-label">Calmness:</span> ${calmnessInfo}</div>
        `
        
        // Display all chicago_ways if available
        if (direction.osmDataChicagoWays && direction.osmDataChicagoWays.length > 0) {
          listItemHtml += `<div><span class="debug-label">Chicago Ways (${direction.osmDataChicagoWays.length}):</span></div>`
          
          // Track which osm_ids have been displayed with buttons in this direction
          const seenOsmIds = new Set()
          
          direction.osmDataChicagoWays.forEach((chicagoWay, idx) => {
            const chicagoWaysInfo = formatChicagoWaysInfo(chicagoWay.osmData)
            const osmWaysInfo = formatOsmWaysInfo(chicagoWay.osmData)
            
            // Format the instruction for this chicago_way
            // Use effectiveName which includes descriptions for unnamed streets (computed in Python)
            const chicagoWayName = chicagoWay.effectiveName || chicagoWay.name || 'an unknown street'
            const instruction = `${chicagoWay.maneuver} ${chicagoWay.cardinal} on ${chicagoWayName} for ${Math.round(chicagoWay.distance)}m`
            
            // Get the feature index for this chicago_way
            const featureIndex = direction.featureIndices[idx]
            
            // Add button for unique osm_ids
            const osmId = chicagoWay.osmData?.osm_id
            let osmWayButton = ''
            if (osmId && !seenOsmIds.has(osmId)) {
              seenOsmIds.add(osmId)
              osmWayButton = `<button class="osm-way-button" data-osm-id="${osmId}" title="Highlight OSM way ${osmId} on map">Highlight OSM way</button>`
            }
            
            // Add button to highlight this specific chicago_way
            const highlightChicagoWayButton = `<button class="osm-way-button" data-chicago-way-index="${featureIndex}" title="Highlight this chicago_way on map">Highlight chicago_way</button>`
            
            const parkName = chicagoWay.osmData?.park_name || 'None'
            
            listItemHtml += `
              <div style="margin-left: 15px; margin-top: 5px;">
                <div><strong>Chicago Way ${idx + 1}:</strong> ${instruction} ${highlightChicagoWayButton} ${osmWayButton}</div>
                <div style="margin-left: 10px;"><span class="debug-label">Chicago Ways:</span> ${chicagoWaysInfo}</div>
                <div style="margin-left: 10px;"><span class="debug-label">OSM Ways:</span> ${osmWaysInfo}</div>
                <div style="margin-left: 10px;"><span class="debug-label">Containing Park:</span> ${parkName}</div>
              </div>
            `
          })
        } else {
          const chicagoWaysInfo = direction.osmData ? formatChicagoWaysInfo(direction.osmData) : 'No data'
          const osmWaysInfo = direction.osmData ? formatOsmWaysInfo(direction.osmData) : 'No data'
          const parkName = direction.osmData?.park_name || 'None'
          
          listItemHtml += `
            <div><span class="debug-label">Chicago Ways Data:</span> ${chicagoWaysInfo}</div>
            <div><span class="debug-label">OSM Ways Data:</span> ${osmWaysInfo}</div>
            <div><span class="debug-label">Containing Park:</span> ${parkName}</div>
          `
        }
        
        listItemHtml += `</div>`
      }
      
      listItemHtml += `</span></li>`
      
      $directionsList.append(listItemHtml)
    })
    
    // Add click handlers to each direction item
    $('.direction-item').on('click', (e) => {
      // Don't trigger if clicking on debug info
      if ($(e.target).closest('.direction-debug-info').length > 0) {
        return
      }
      
      const $clickedItem = $(e.currentTarget)
      const directionIndex = $clickedItem.data('direction-index')
      const direction = directions[directionIndex]
      
      if (direction && direction.featureIndices) {
        // Check if this item is already selected
        const isAlreadySelected = $clickedItem.hasClass('selected')
        
        if (isAlreadySelected) {
          // Unhighlight: remove selected class and styles, remove highlight layers, show full route
          $clickedItem.removeClass('selected').css({
            'background-color': '',
            'border-left-color': ''
          })
          
          // Remove highlight layers
          if (this.highlightLayer) {
            this.map.removeLayer(this.highlightLayer)
            this.highlightLayer = null
          }
          if (this.highlightGlowLayer) {
            this.map.removeLayer(this.highlightGlowLayer)
            this.highlightGlowLayer = null
          }
          
          // Fit map to show the full route
          if (this.directionsRouteLayer) {
            this.map.fitBounds(this.directionsRouteLayer.getBounds())
          }
        } else {
          // Remove selected class and styles from all direction items
          $('.direction-item').removeClass('selected').css({
            'background-color': '',
            'border-left-color': ''
          })
          
          // Get the color for this direction
          const color = $clickedItem.data('color')
          const lightColor = this.getLightColor(color)
          
          // Add selected class and color-based styles to the clicked item
          $clickedItem.addClass('selected').css({
            'background-color': lightColor,
            'border-left-color': color
          })
          
          // Highlight the chicago_ways on the map
          this.highlightChicagoWays(direction.featureIndices)
          
          // Scroll to the map smoothly (only on mobile)
          const isMobileScreen = $(window).outerWidth() <= 768
          const mapElement = document.getElementById('map')
          if (mapElement && isMobileScreen) {
            mapElement.scrollIntoView({ behavior: 'smooth', block: 'start' })
          }
        }
      }
    })
    
    // Add click handlers for OSM way buttons
    $('.osm-way-button').on('click', (e) => {
      e.stopPropagation() // Prevent triggering the direction-item click
      
      const $button = $(e.currentTarget)
      const osmId = $button.data('osm-id')
      const chicagoWayIndex = $button.data('chicago-way-index')
      
      // Handle chicago_way highlighting
      if (chicagoWayIndex !== undefined) {
        this.highlightChicagoWays([chicagoWayIndex])
        
        // Scroll to the map smoothly (only on mobile)
        const isMobileScreen = $(window).outerWidth() <= 768
        const mapElement = document.getElementById('map')
        if (mapElement && isMobileScreen) {
          mapElement.scrollIntoView({ behavior: 'smooth', block: 'start' })
        }
        return
      }
      
      // Handle OSM way display
      if (!osmId) {
        return
      }
      
      // Fetch the full OSM way geometry from the API
      $.getJSON(`/api/osm-way/?osm_id=${osmId}`)
        .done((data) => {
          this.highlightOsmWay(data)
          
          // Scroll to the map smoothly (only on mobile)
          const isMobileScreen = $(window).outerWidth() <= 768
          const mapElement = document.getElementById('map')
          if (mapElement && isMobileScreen) {
            mapElement.scrollIntoView({ behavior: 'smooth', block: 'start' })
          }
        })
        .fail((jqxhr, textStatus, error) => {
          console.error('Failed to fetch OSM way:', textStatus, error)
          alert(`Failed to load OSM way ${osmId}: ${error}`)
        })
    })
    
    // Reposition the container based on screen size
    // This will handle showing/hiding directions appropriately for mobile vs desktop
    this.positionDirectionsContainer()
    
    // On mobile, reset the explicit show state when new directions are displayed
    const isMobileScreen = $(window).outerWidth() <= 768
    if (isMobileScreen) {
      this.mobileDirectionsShown = false
    }
  }

  hideDirections() {
    const $directionsContainer = $('#mobile-directions-container')
    const $directionsList = $('#directions-list')
    
    $directionsContainer.hide()
    $directionsList.empty()
    
    // Reset mobile state
    this.mobileDirectionsShown = false
    
    // Update mobile button visibility
    this.updateMobileDirectionsButtons()
  }

  highlightChicagoWays(featureIndices) {
    // Remove any existing highlight
    if (this.highlightLayer) {
      this.map.removeLayer(this.highlightLayer)
    }
    if (this.highlightGlowLayer) {
      this.map.removeLayer(this.highlightGlowLayer)
    }

    if (!this.routeData || !featureIndices || featureIndices.length === 0) {
      return
    }

    // Create a GeoJSON with only the selected features
    const selectedFeatures = featureIndices.map(idx => this.routeData.features[idx])
    const highlightGeoJSON = {
      type: 'FeatureCollection',
      features: selectedFeatures
    }

    // Create glow layer first (wider, semi-transparent)
    this.highlightGlowLayer = L.geoJSON(highlightGeoJSON, {
      style: (feature) => {
        const color = this.getLineColor(feature.properties.type)
        return {
          weight: 16,
          color: color,
          opacity: 0.3
        }
      },
      onEachFeature: function (feature, layer) {
        // Bind popup to allow tooltips on highlighted segments
        layer.bindPopup(
          `<strong>Name:</strong> ${feature.properties.name}<br>` +
          `<strong>Type:</strong> ${feature.properties.type ? feature.properties.type : 'non-mellow street'}`
        )
      }
    }).addTo(this.map)
    
    // Create main highlight layer on top (narrower, fully opaque)
    this.highlightLayer = L.geoJSON(highlightGeoJSON, {
      style: (feature) => {
        const color = this.getLineColor(feature.properties.type)
        return {
          weight: 8,
          color: color,
          opacity: 1
        }
      },
      onEachFeature: function (feature, layer) {
        // Bind popup to allow tooltips on highlighted segments
        layer.bindPopup(
          `<strong>Name:</strong> ${feature.properties.name}<br>` +
          `<strong>Type:</strong> ${feature.properties.type ? feature.properties.type : 'non-mellow street'}`
        )
      }
    }).addTo(this.map)

    // Fit the map to show the highlighted chicago_ways
    this.map.fitBounds(this.highlightLayer.getBounds(), { padding: [50, 50] })
  }

  highlightOsmWay(osmWayFeature) {
    // Remove any existing highlight
    if (this.highlightLayer) {
      this.map.removeLayer(this.highlightLayer)
    }
    if (this.highlightGlowLayer) {
      this.map.removeLayer(this.highlightGlowLayer)
    }

    if (!osmWayFeature || !osmWayFeature.geometry) {
      return
    }

    // Create glow layer for the OSM way
    this.highlightGlowLayer = L.geoJSON(osmWayFeature, {
      style: () => {
        return {
          weight: 14,
          color: '#9b59b6', // Purple color for OSM ways
          opacity: 0.3
        }
      }
    }).addTo(this.map)

    // Create and add the highlight layer for the full OSM way
    // Use a distinct color (purple/magenta) to distinguish from chicago_ways
    this.highlightLayer = L.geoJSON(osmWayFeature, {
      style: () => {
        return {
          weight: 6,
          color: '#9b59b6', // Purple color for OSM ways
          opacity: 0.9
        }
      }
    }).addTo(this.map)

    // Fit the map to show the highlighted OSM way
    this.map.fitBounds(this.highlightLayer.getBounds(), { padding: [50, 50] })
  }
}
