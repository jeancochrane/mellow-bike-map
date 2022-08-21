import UserLocations from './userlocations.js'
import autocomplete from './autocomplete.js'
import Geolocation from './geolocation.js'
// The App class holds top level state and map related methods that other modules
// need to call, for example to update the position of markers.
export default class App {
  constructor(routeListUrl, routeUrl) {
    this.routeListUrl = routeListUrl
    this.routeUrl = routeUrl

    this.routeLayer = null
    this.allRoutesLayer = null
    this.markers = { 'source': null, 'target': null }

    // Start the app once the DOM is ready
    document.addEventListener('DOMContentLoaded', this.start.bind(this))
  }

  start() {
    // Create the leaflet map
    this.map = this.createMap()

    // Store references to DOM elements we'll need
    const $directionsForm = $('#input-elements')
    const sourceCoordsElem = document.getElementById('source')
    const sourceTextInput = document.getElementById('source_text')

    const targetCoordsElem = document.getElementById('target')
    const targetTextInput = document.getElementById('target_text')

    // This uses the same keys as the `markers` object for convenience
    // in the code below
    this.directionsFormElements = {
      source: {
        coords: sourceCoordsElem,
        input: sourceTextInput,
        autocomplete: null
      },
      target: {
        coords: targetCoordsElem,
        input: targetTextInput,
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
    this.userLocations = new UserLocations(this)

    // Load the routes layer from the backend
    this.loadAllRoutes()

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
    autocomplete.addDefaultOption(this, this.gpsLocationString)
  }

  // Fetch the layer of annotated routes from the backend and display it on the map
  loadAllRoutes() {
    // Start spinner while we retrieve initial route map
    this.map.spin(true)
    $.getJSON(this.routeListUrl).done((data) => {
      this.allRoutesLayer = L.geoJSON(data, {
        style: (feature) => {
          return { color: this.getLineColor(feature.properties.type), opacity: 0.6 }
        },
        interactive: false,
      }).addTo(this.map)
      this.map.spin(false)
    }).fail(function (jqxhr, textStatus, error) {
      console.log(textStatus + ': ' + error)
    })
  }

  // Create a legend
  createLegend() {
    const legend = L.control({ position: 'bottomright' })
    legend.onAdd = (map) => {
      let div = L.DomUtil.create('div', 'info legend hideable-legend')
      const routeTypes = [
        ['path', 'Off-street bike paths (very calm)'],
        ['street', 'Mellow streets (calm)'],
        ['route', 'Main streets, often with bike lanes (less calm)']
      ]
      for (const routeType of routeTypes) {
        const color = this.getLineColor(routeType[0])
        const description = routeType[1]
        div.innerHTML += `<i style="background:${color}"></i>${description}`
        if (routeType !== routeTypes[routeTypes.length - 1]) {
          div.innerHTML += '<br>'
        }
      }
      return div
    }
    return legend
  }

  getLineColor(type) {
    switch (type) {
      case 'street': return '#77b7a2'
      case 'route': return '#e18a7e'
      case 'path': return '#e17fa8'
      default: return '#7ea4e1'
    }
  }

  // Clear the form and remove plotted directions from the map
  reset() {
    if (this.routeLayer) { this.map.removeLayer(this.routeLayer) }
    if (this.markers['source']) { this.map.removeLayer(this.markers['source']) }
    if (this.markers['target']) { this.map.removeLayer(this.markers['target']) }
    this.allRoutesLayer.setStyle({ opacity: 0.6 })
    $('#source, #source_text, #target, #target_text').val('')
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
    const source = this.directionsFormElements.source.coords.value
    const target = this.directionsFormElements.target.coords.value
    const enableV2 = $('#enable-v2').is(':checked')
    if (source === '') {
      alert('Source is required for search')
    } else if (target == '') {
      alert('Target is required for search')
    } else {
      this.map.spin(true)
      $.getJSON(this.routeUrl + '?' + $.param({ source, target, enable_v2: enableV2 })).done((data) => {
        if (this.routeLayer) {
          this.map.removeLayer(this.routeLayer)
        }
        this.routeLayer = L.geoJSON(data.route, {
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
        this.allRoutesLayer.setStyle({ opacity: 0.3 })
        this.map.fitBounds(this.routeLayer.getBounds())
        this.showRouteEstimate(data.route.properties.distance, data.route.properties.time)
      }).fail((jqxhr, textStatus, error) => {
        const err = textStatus + ': ' + error
        alert('Request failed: ' + err)
      }).always(() => {
        this.map.spin(false)
      })
    }
  }

  // Creates a marker or moves an existing one to a new location and updates
  // the associated hidden <input> that stores the location. If addressString
  // is supplied, also updates the visible <input> with the given string.
  // markerName should be one of 'source', or 'target'
  setMarkerLocation(markerName, lat, lng, addressString = '') {
    // Create the marker if it doesn't exist
    if (!this.markers[markerName]) {
      this.markers[markerName] = L.marker([lat, lng]).addTo(this.map)
    } else {
      // Move it to the new location if it does
      this.markers[markerName].setLatLng({
        lat: lat,
        lng: lng
      })
    }

    const { input, coords } = this.directionsFormElements[markerName]

    // Update the coordinates
    coords.value = `${lat},${lng}`

    if (addressString) {
      // Update the marker's popup
      this.markers[markerName].unbindPopup().bindPopup(addressString)
      // Update the user-facing text input field
      input.value = addressString
    }

    this.map.setView([lat, lng])
  }

  zoomToLocation(lat, lng) {
    this.map.setView([lat, lng], 14)
  }

  setSourceLocation(lat, lng, addressString) {
    this.setMarkerLocation('source', lat, lng, addressString)
  }

  setTargetLocation(lat, lng, addressString) {
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
