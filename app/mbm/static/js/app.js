import UserLocations from './userlocations.js'
import autocomplete from './autocomplete.js'
import Geolocation from './geolocation.js'
import { getUserPreferences, saveUserPreferences } from './storage.js'
import { directionsList } from './turnbyturn.js'
// The App class holds top level state and map related methods that other modules
// need to call, for example to update the position of markers.
export default class App {
  constructor(routeListUrl, routeUrl, fromAddress = '', toAddress = '') {
    this.routeListUrl = routeListUrl
    this.routeUrl = routeUrl
    this.fromAddress = fromAddress
    this.toAddress = toAddress

    this.routeLayer = null
    this.allRoutesLayer = null
    this.markers = { 'source': null, 'target': null }
    this.routeData = null
    this.highlightLayer = null
    this.highlightGlowLayer = null

    // Start the app once the DOM is ready
    document.addEventListener('DOMContentLoaded', this.start.bind(this))
    this.sourceLocation = ''
    this.targetLocation = ''
    this.sourceAddressString = ''
    this.targetAddressString = ''
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
    autocomplete.addCustomOption(this, this.gpsLocationString, (markerName) => {
      const latlng = this.geolocation.marker.getLatLng()
      this.setSourceOrTargetLocation(markerName, latlng.lat, latlng.lng, this.gpsLocationString)
    })

    // If from/to addresses are provided in the URL, geocode them and auto-run search
    if (this.fromAddress && this.toAddress) {
      this.geocodeAddressesAndRunSearch(this.fromAddress, this.toAddress)
    }
  }

  // When addresses are provided in the URL, we don't have coordinates returned
  // from Google Maps API as we do when selecting addresses from autocomplete,
  // so we need to geocode the addresses by calling the Google Maps API.
  geocodeAddressesAndRunSearch(fromAddress, toAddress) {
    const geocoder = new google.maps.Geocoder()
    
    // Geocode the source address
    geocoder.geocode({ address: fromAddress }, (results, status) => {
      if (status === 'OK' && results[0]) {
        const sourceLat = results[0].geometry.location.lat()
        const sourceLng = results[0].geometry.location.lng()
        this.setSourceLocation(sourceLat, sourceLng, fromAddress)
        
        // Once source is set, geocode the target
        geocoder.geocode({ address: toAddress }, (results, status) => {
          if (status === 'OK' && results[0]) {
            const targetLat = results[0].geometry.location.lat()
            const targetLng = results[0].geometry.location.lng()
            this.setTargetLocation(targetLat, targetLng, toAddress)
            
            // Auto-submit the search
            $('#input-elements').submit()
          } else {
            console.error('Geocode failed for target address:', status)
            alert('Could not find the destination address: ' + toAddress)
          }
        })
      } else {
        console.error('Geocode failed for source address:', status)
        alert('Could not find the start address: ' + fromAddress)
      }
    })
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
    if (this.routeLayer) { this.map.removeLayer(this.routeLayer) }
    if (this.highlightLayer) { this.map.removeLayer(this.highlightLayer) }
    if (this.highlightGlowLayer) { this.map.removeLayer(this.highlightGlowLayer) }
    if (this.markers['source']) { this.map.removeLayer(this.markers['source']) }
    if (this.markers['target']) { this.map.removeLayer(this.markers['target']) }
    this.allRoutesLayer.setStyle({ opacity: 0.6 })
    this.hideRouteEstimate()
    this.hideDirections()
    this.sourceAddressString = ''
    this.targetAddressString = ''
    this.routeData = null
    // Clear the URL back to home, but preserve query parameters (like ?debug=true)
    const searchParams = new URLSearchParams(window.location.search)
    const queryString = searchParams.toString()
    window.history.pushState({}, '', '/' + (queryString ? '?' + queryString : ''))
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
      // Update URL with from/to addresses
      // Use the stored address strings, or fall back to the input values
      const fromAddr = this.sourceAddressString
      const toAddr = this.targetAddressString 
      
      if (fromAddr && toAddr) {
        // Preserve existing query parameters (like ?debug=true)
        const searchParams = new URLSearchParams(window.location.search)
        const queryString = searchParams.toString()
        const newUrl = `/from/${encodeURIComponent(fromAddr)}/to/${encodeURIComponent(toAddr)}/${queryString ? '?' + queryString : ''}`
        window.history.pushState({}, '', newUrl)
      }
      
      this.map.spin(true)
      $.getJSON(this.routeUrl + '?' + $.param({ source, target, enable_v2: enableV2 })).done((data) => {

        // Store the route data for highlighting
        this.routeData = data.route
        
        const directions = directionsList(data.route.features)
        this.displayDirections(directions)

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
    const $directionsContainer = $('#directions-container')
    
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
      let directionText = ''
      if (index === 0) {
        let streetName = direction.name || 'an unknown street'
        directionText = `Head ${direction.cardinal} on ${streetName} for ${formatDistance(direction.distance)}`
      } else {
        let streetName = direction.name || 'an unknown street'
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
            const chicagoWayName = chicagoWay.name || 'an unknown street'
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
            
            listItemHtml += `
              <div style="margin-left: 15px; margin-top: 5px;">
                <div><strong>Chicago Way ${idx + 1}:</strong> ${instruction} ${highlightChicagoWayButton} ${osmWayButton}</div>
                <div style="margin-left: 10px;"><span class="debug-label">Chicago Ways:</span> ${chicagoWaysInfo}</div>
                <div style="margin-left: 10px;"><span class="debug-label">OSM Ways:</span> ${osmWaysInfo}</div>
              </div>
            `
          })
        } else {
          const chicagoWaysInfo = direction.osmData ? formatChicagoWaysInfo(direction.osmData) : 'No data'
          const osmWaysInfo = direction.osmData ? formatOsmWaysInfo(direction.osmData) : 'No data'
          
          listItemHtml += `
            <div><span class="debug-label">Chicago Ways Data:</span> ${chicagoWaysInfo}</div>
            <div><span class="debug-label">OSM Ways Data:</span> ${osmWaysInfo}</div>
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
        
        // Scroll to the map smoothly
        const mapElement = document.getElementById('map')
        if (mapElement) {
          mapElement.scrollIntoView({ behavior: 'smooth', block: 'start' })
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
        
        // Scroll to the map smoothly
        const mapElement = document.getElementById('map')
        if (mapElement) {
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
          
          // Scroll to the map smoothly
          const mapElement = document.getElementById('map')
          if (mapElement) {
            mapElement.scrollIntoView({ behavior: 'smooth', block: 'start' })
          }
        })
        .fail((jqxhr, textStatus, error) => {
          console.error('Failed to fetch OSM way:', textStatus, error)
          alert(`Failed to load OSM way ${osmId}: ${error}`)
        })
    })
    
    // Show the directions container
    $directionsContainer.show()
  }

  hideDirections() {
    const $directionsContainer = $('#directions-container')
    const $directionsList = $('#directions-list')
    
    $directionsContainer.hide()
    $directionsList.empty()
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
