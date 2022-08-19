import UserLocations from './userlocations.js'
import { initAutocomplete } from './autocomplete.js'
// The MBM class holds top level state and map related methods that other modules
// need to call, for example to update the position of markers. It could reasonably
// be called "Map", but that might cause confusion with the leaflet `L.map` object
// that we call map.
export default class MBM {
  constructor() {
    // Get variables written to the page by the Django backend
    const routeListUrl = context.routeListUrl
    const routeUrl = context.routeUrl

    const getLineColor = (type) => {
      switch (type) {
        case 'street': return '#77b7a2'
        case 'route': return '#e18a7e'
        case 'path': return '#e17fa8'
        default: return '#7ea4e1'
      }
    }

    this.$routeEstimate = $('#route-estimate')

    const googleStyles = [
      {
        stylers: [
          {saturation: -100},
          {lightness: 40}
        ]
      },
      {
        featureType: 'poi',
        elementType: 'labels',
        stylers: [{visibility: 'off'}]
      },
      {
        featureType: 'transit',
        elementType: 'labels',
        stylers: [{visibility: 'off'}]
      },
      {
        featureType: 'administrative.neighborhood',
        elementType: 'labels',
        stylers: [{visibility: 'off'}]
      },
      {
        featureType: 'road.highway',
        elementType: 'labels',
        stylers: [{visibility: 'off'}]
      },
    ]

    document.addEventListener('DOMContentLoaded', (event) => {
      $('[data-toggle="tooltip"]').tooltip()
      
      const map = L.map('map')
      this.map = map

      // Load basemap
      const streets = new L.Google('ROADMAP', {mapOptions: {styles: googleStyles}})
      map.addLayer(streets).setView([41.87, -87.62], 11);
      
      let routeLayer, allRoutesLayer  // Init empty layers
      this.markers = {'source': undefined, 'target': undefined}  // Init marker
      
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
          autocomplete: undefined
        },
        target: {
          coords: targetCoordsElem,
          input: targetTextInput,
          autocomplete: undefined
        }
      }

      this.gpsLocationString = 'My position'
      
      const isMobileScreen = $(window).outerWidth() <= 768

      // Make sure the map fits the full height of the screen
      $(window).resize(function () {
        var windowHeight = $(window).innerHeight()
        var offsetTop = $('.navbar')[0].offsetHeight
        // Add controls to the top offset on mobile screens, where they merge
        // with the navbar
        if (isMobileScreen) { offsetTop += $('#controls-container')[0].offsetHeight }
        var mapHeight = windowHeight - offsetTop
        $('#map').css('height', mapHeight)
      }).resize();

      // Manually trigger map resize when controls are toggled
      $directionsForm.on('shown.bs.collapse hidden.bs.collapse', function(e) {
        $(window).resize()
      })

      // Create a legend
      const legend = L.control({position: 'bottomright'})
      legend.onAdd = (map) => {
        let div = L.DomUtil.create('div', 'info legend hideable-legend')
        const routeTypes = [
          ['path', 'Off-street bike paths (very calm)'],
          ['street', 'Mellow streets (calm)'],
          ['route', 'Main streets, often with bike lanes (less calm)']
        ]
        for (const routeType of routeTypes) {
          const color = getLineColor(routeType[0])
          const description = routeType[1]
          div.innerHTML += `<i style="background:${color}"></i>${description}`
          if (routeType !== routeTypes[routeTypes.length-1]) {
            div.innerHTML += '<br>'
          }
        }
        return div
      }
      legend.addTo(map)

      this.userLocations = new UserLocations(this)

      // Start spinner while we retrieve initial route map
      map.spin(true)
      $.getJSON(routeListUrl).done(function(data) {
        allRoutesLayer = L.geoJSON(data, {
          style: function(feature) {
            return {color: getLineColor(feature.properties.type), opacity: 0.6}
          },
          interactive: false,
        }).addTo(map)
        map.spin(false)
      }).fail(function(jqxhr, textStatus, error) {
        console.log(textStatus + ': ' + error)
      })

      // Define behavior for the search button
      const search = (e) => {
        e.preventDefault()
        const source = sourceCoordsElem.value
        const target = targetCoordsElem.value
        const enableV2 = $('#enable-v2').is(':checked')
        if (source === '') {
          alert('Source is required for search')
        } else if (target == '') {
          alert('Target is required for search')
        } else {
          this.map.spin(true)
          $.getJSON(routeUrl + '?' + $.param({source, target, enable_v2: enableV2})).done(function(data) {
            if (routeLayer) {
              this.map.removeLayer(routeLayer)
            }
            routeLayer = L.geoJSON(data.route, {
              style: function(feature) {
                return {weight: 5, color: getLineColor(feature.properties.type)}
              },
              onEachFeature: function(feature, layer) {
                layer.bindPopup(
                  `<strong>Name:</strong> ${feature.properties.name}<br>` +
                  `<strong>Type:</strong> ${feature.properties.type ? feature.properties.type : 'non-mellow street'}`
                )
              }
            }).addTo(this.map)
            // Lower opacity on non-route street colors
            allRoutesLayer.setStyle({opacity: 0.3})
            this.map.fitBounds(routeLayer.getBounds())
            this.showRouteEstimate(data.route.properties.distance, data.route.properties.time)
          }.bind(this)).fail(function(jqxhr, textStatus, error) {
            const err = textStatus + ': ' + error
            alert('Request failed: ' + err)
          }).always(function() {
            this.map.spin(false)
          }.bind(this))
        }
      }

      $directionsForm.submit(search)

      // Define behavior for the "Reset search" button
      $('#reset-search').click(function(e) {
        if (routeLayer) { map.removeLayer(routeLayer) }
        if (this.markers['source']) { map.removeLayer(this.markers['source']) }
        if (this.markers['target']) { map.removeLayer(this.markers['target']) }
        allRoutesLayer.setStyle({opacity: 0.6})
        $('#source, #source_text, #target, #target_text').val('')
        this.hideRouteEstimate()
      })

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
      this.$hideSearch.click(function(e) {
        $(window).resize()
        toggleControlText(this, 'Search for a route', 'Hide search box')
      })

      this.$hideLegend = $('#hide-legend')
      this.$hideLegend.click(function(e) {
        toggleControlElement(this, '.hideable-legend')
        toggleControlText(this, 'Show legend', 'Hide legend')
      })

      // Show the search box by default on desktop
      if (!isMobileScreen) { this.$hideSearch.click() }

      this.startGPSTracking()

      for (const [name, {input}] of Object.entries(this.directionsFormElements)) {
        this.directionsFormElements[name]['autocomplete'] = initAutocomplete(input, name, this)
      }

      // This is a very overcomplicated way to put our own items into the
      // autocomplete comboboxes. There doesn't seem to be any official way to do this
      // other than completely implementing the autocomplete widget yourself, thus our hacks.
      //
      // TODO: Add user locations, filter by user input, make keyboard interaction work

      // The google autocomplete container doesn't have any obvious way to find the
      // input associated with the list of options, which makes it difficult to write
      // a handler for a user selecting one of our preset options (which input and coords
      // element should we update?). So instead, we keep track of which input element
      // received a focus event most recently and update that one when
      let lastFocusedInput
      const recordFocusEvent = (event) => {
        lastFocusedInput = event.target
      }

      sourceTextInput.addEventListener('focus', recordFocusEvent)
      targetTextInput.addEventListener('focus', recordFocusEvent)

      const gpsLocationOption = $(`
        <div class="pac-item" tabindex="0">
          <span class="pac-icon pac-icon-marker"></span>
          <span class="pac-item-query">${this.gpsLocationString}</span>
        </div>
      `).on('mousedown', () => {
        lastFocusedInput.value = this.gpsLocationString
      })
      $('.pac-container').append(gpsLocationOption)

      // Watch the body element for the addition of new child nodes. Once the
      // autocomplete containers are present, append our options to the list,
      // then remove the observer.
      const observer = new MutationObserver((mutations, observer) => {
        // Add our preset locations to the list
        const autocompleteContainers = $('.pac-container')
        if (autocompleteContainers.length == 2) {
          autocompleteContainers.append(gpsLocationOption)
          observer.disconnect()
        }
      })

      observer.observe(document.body, {
        childList: true
      })
    })
  }

  startGPSTracking() {
    if (navigator.geolocation) {
      navigator.geolocation.watchPosition(this.handleGPSPositionUpdate.bind(this))
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

    const {input, coords} = this.directionsFormElements[markerName]

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

  // Continuously update marker as position changes when the
  // user selects the GPS location option for the navigation
  // source or target
  handleGPSPositionUpdate(position) {
    for (const [name, {input}] of Object.entries(this.directionsFormElements)) {
      // Only update the source marker if the user is using their current location
      // as the source location
      if (input.value != this.gpsLocationString) {
        continue
      }
      this.setMarkerLocation(name, position.coords.latitude, position.coords.longitude, this.gpsLocationString)
      this.zoomToLocation(position.coords.latitude, position.coords.longitude)
    }
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

const mbm = new MBM()
