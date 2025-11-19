import UserLocations from './userlocations.js'
import autocomplete from './autocomplete.js'
import Geolocation from './geolocation.js'
import { getUserPreferences, saveUserPreferences } from './storage.js'
// The App class holds top level state and map related methods that other modules
// need to call, for example to update the position of markers.
export default class App {
  constructor(routeListUrl, routeUrl) {
    this.routeListUrl = routeListUrl
    this.routeUrl = routeUrl

    this.directionsRouteLayer = null
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

  // Clear the form and remove plotted directions from the map
  // Inputs are automatically reset because the button that triggers this has `type="reset"`
  reset() {
    if (this.directionsRouteLayer) { this.map.removeLayer(this.directionsRouteLayer) }
    if (this.markers['source']) { this.map.removeLayer(this.markers['source']) }
    if (this.markers['target']) { this.map.removeLayer(this.markers['target']) }
    this.calmRoutesLayer.setStyle({ opacity: 0.6 })
    this.hideRouteEstimate()
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
    const source = this.sourceLocation
    const target = this.targetLocation
    const enableV2 = $('#enable-v2').is(':checked')
    if (source === '') {
      alert('Source is required for search')
    } else if (target == '') {
      alert('Target is required for search')
    } else {
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
        this.showRouteEstimate(data.route.properties.distance, data.route.properties.time)
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
        // Update the marker's popup
        this.markers[markerName].unbindPopup().bindPopup(addressString)
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
    this.setMarkerLocation('source', lat, lng, addressString)
  }

  setTargetLocation(lat, lng, addressString) {
    this.targetLocation = this.serializeLocation(lat, lng)
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

  showRouteEstimate(distance, time) {
    this.$routeEstimate.html(`<strong>${time}</strong> (${distance})`)
    this.$routeEstimate.show()
    this.$hideSearch.addClass('mt-1')
    this.$hideLegend.addClass('mt-1')
  }

  hideRouteEstimate() {
    this.$routeEstimate.hide()
    this.$routeEstimate.html('')
    this.$hideSearch.removeClass('mt-1')
    this.$hideLegend.removeClass('mt-1')
  }
}
