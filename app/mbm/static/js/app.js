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

const showRouteEstimate = (distance, time) => {
  $('#route-estimate').html(`<strong>${time}</strong> (${distance})`)
  $('#route-estimate').show()
  $('#hide, #hide-legend').addClass('mt-1')
}

const hideRouteEstimate = () => {
  $('#route-estimate').hide()
  $('#route-estimate').html('')
  $('#hide, #hide-legend').removeClass('mt-1')
}

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
  $('#input-elements').on('shown.bs.collapse hidden.bs.collapse', function(e) {
    $(window).resize()
  })

  // Load basemap
  const streets = new L.Google('ROADMAP', {mapOptions: {styles: googleStyles}})
  map.addLayer(streets).setView([41.87, -87.62], 11);

  let routeLayer, allRoutesLayer  // Init empty layers
  let markers = {'source': undefined, 'target': undefined}  // Init marker

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
  $('#submit').click(function(e) {
    const source = $('#source').val()
    const target = $('#target').val()
    const enableV2 = $('#enable-v2').is(':checked')
    if (source === '') {
      alert('Source is required for search')
    } else if (target == '') {
      alert('Target is required for search')
    } else {
      map.spin(true)
      $.getJSON(routeUrl + '?' + $.param({source, target, enable_v2: enableV2})).done(function(data) {
        if (routeLayer) {
          map.removeLayer(routeLayer)
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
        }).addTo(map)
        // Lower opacity on non-route street colors
        allRoutesLayer.setStyle({opacity: 0.3})
        map.fitBounds(routeLayer.getBounds())
        showRouteEstimate(data.route.properties.distance, data.route.properties.time)
      }).fail(function(jqxhr, textStatus, error) {
        const err = textStatus + ': ' + error
        alert('Request failed: ' + err)
      }).always(function() {
        map.spin(false)
      })
    }
  })

  // Define behavior for the "Reset search" button
  $('#reset-search').click(function(e) {
    if (routeLayer) { map.removeLayer(routeLayer) }
    if (markers['source']) { map.removeLayer(markers['source']) }
    if (markers['target']) { map.removeLayer(markers['target']) }
    allRoutesLayer.setStyle({opacity: 0.6})
    $('#source, #source_text, #target, #target_text').val('')
    hideRouteEstimate()
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

  // Toggle text on Show/Hide button
  $('#hide').click(function(e) {
    $(window).resize()
    toggleControlText(this, 'Search for a route', 'Hide search box')
  })
  $('#hide-legend').click(function(e) {
    toggleControlElement(this, '.hideable-legend')
    toggleControlText(this, 'Show legend', 'Hide legend')
  })

  // Show the search box by default on desktop
  if (!isMobileScreen) { $('#hide').click() }

  // Address components for autocomplete
  const canonicalComponents = [
    ['street_number', 'short_name', ' '],
    ['route', 'long_name', ', '],
    ['locality', 'long_name', ', '],
    ['administrative_area_level_1', 'short_name', ' '],
    ['postal_code', 'short_name', '']
  ]

  const zoomToLocation = (lat, lng) => {
    map.setView([lat, lng], 14)
  }

  const initAutocomplete = (textElementId, coordElementId, marker, shouldZoom = false) => {
    // Create the autocomplete object
    let autocomplete = new google.maps.places.Autocomplete(
      document.getElementById(textElementId), {
        componentRestrictions: { country: "us" },
      }
    )
    // Avoid paying for data that you don't need by restricting the set of
    // place fields that are returned to just the address components.
    autocomplete.setFields(['address_component', 'geometry'])
    // When the user selects an address from the drop-down, populate the
    // address fields in the form.
    autocomplete.addListener('place_changed', () => {
      // Get the place details from the autocomplete object.
      const place = autocomplete.getPlace()

      const lat = place.geometry.location.lat()
      const lng = place.geometry.location.lng()
      document.getElementById(coordElementId).value = `${lat},${lng}`

      // Get each component of the address from the place details,
      // and then fill-in the corresponding field on the form.
      let addressString = ''
      for (const canonicalComponent of canonicalComponents) {
        const componentId = canonicalComponent[0]
        const componentType = canonicalComponent[1]
        const componentSuffix = canonicalComponent[2]
        for (const addressComponent of place['address_components']) {
          if (addressComponent.types.includes(componentId)) {
            addressString += addressComponent[componentType] + componentSuffix
            break
          }
        }
      }
      document.getElementById(textElementId).value = addressString

      if (markers[marker]) {map.removeLayer(markers[marker])}
      markers[marker] = L.marker([lat, lng]).bindPopup(addressString).addTo(map)
      map.setView([lat, lng])
    });

    // Bias the autocomplete object to the user's geographical location,
    // as supplied by the browser's 'navigator.geolocation' object.
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(position => {
        const geolocation = {
          lat: position.coords.latitude,
          lng: position.coords.longitude
        }
        if (shouldZoom) {
          document.getElementById('source').value = `${geolocation['lat']},${geolocation['lng']}`
          document.getElementById('source_text').value = 'My position'
          if (markers['source']) {map.removeLayer(markers['source'])}
          markers['source'] = L.marker(
            [geolocation['lat'], geolocation['lng']]
          ).bindPopup('My position').addTo(map)
          zoomToLocation(geolocation.lat, geolocation.lng)
        }
        const circle = new google.maps.Circle({
          center: geolocation,
          radius: position.coords.accuracy
        })
        autocomplete.setBounds(circle.getBounds())
      })
    }
  }

  // Moves "source" marker to a new location, updates the source input that
  // stores the location, and zooms to the new location
  const updateSourceLocation = position => {
    markers['source'].setLatLng({
      lat: position.coords.latitude,
      lng: position.coords.longitude
    })
    document.getElementById('source').value = `${position.coords.latitude},${position.coords.longitude}`
    zoomToLocation(position.coords.latitude, position.coords.longitude)
  }

  // Continually update the "source" marker with the user's location if th
  if (navigator.geolocation) {
    navigator.geolocation.watchPosition(position => {
      if (!markers['source']) {
        return
      }
      // Only update the source marker if the user is using their current location
      // as the source location
      if (document.getElementById('source_text').value != 'My position') {
        return
      }
      updateSourceLocation(position)
      console.log(`Updated position to (${position.coords.latitude},${position.coords.longitude})`)
    })
  }

  initAutocomplete('source_text', 'source', 'source', true)
  initAutocomplete('target_text', 'target', 'target')
})
