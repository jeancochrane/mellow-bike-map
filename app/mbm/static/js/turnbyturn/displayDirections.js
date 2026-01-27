export function displayDirections(app, directions) {
  const $directionsList = $('#directions-list')

  // Clear any existing directions
  $directionsList.empty()

  // Check if debug mode is enabled
  const urlParams = new URLSearchParams(window.location.search)
  const debugMode = urlParams.get('debug') === 'true'

  // Process and add each direction
  directions.forEach((direction, index) => {
    // Determine maneuver for first direction
    const maneuver = index === 0 ? 'Continue' : direction.maneuver

    // Get the color based on the type
    const color = app.getLineColor(direction.type)

    // Get the icon with the appropriate color
    const icon = getDirectionIcon(maneuver, color)

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
      directionText += ' until you reach your destination'
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
        if (app.highlightLayer) {
          app.map.removeLayer(app.highlightLayer)
          app.highlightLayer = null
        }
        if (app.highlightGlowLayer) {
          app.map.removeLayer(app.highlightGlowLayer)
          app.highlightGlowLayer = null
        }

        // Fit map to show the full route
        if (app.directionsRouteLayer) {
          app.map.fitBounds(app.directionsRouteLayer.getBounds())
        }
      } else {
        // Remove selected class and styles from all direction items
        $('.direction-item').removeClass('selected').css({
          'background-color': '',
          'border-left-color': ''
        })

        // Get the color for this direction
        const color = $clickedItem.data('color')
        const lightColor = getLightColor(color)

        // Add selected class and color-based styles to the clicked item
        $clickedItem.addClass('selected').css({
          'background-color': lightColor,
          'border-left-color': color
        })

        // Highlight the chicago_ways on the map
        app.highlightChicagoWays(direction.featureIndices)

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
      app.highlightChicagoWays([chicagoWayIndex])

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
        app.highlightOsmWay(data)

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
  app.positionDirectionsContainer()

  // On mobile, reset the explicit show state when new directions are displayed
  const isMobileScreen = $(window).outerWidth() <= 768
  if (isMobileScreen) {
    app.mobileDirectionsShown = false
  }
}

function getDirectionIcon(maneuver, color) {
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

function formatChicagoWaysInfo(osmData) {
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

function formatOsmWaysInfo(osmData) {
  if (!osmData || !osmData.osm_tags) return ''

  if (Object.keys(osmData.osm_tags).length > 0) {
    const tagStrings = Object.entries(osmData.osm_tags)
      .map(([key, value]) => `${key}=${value}`)
      .join(', ')
    return `{${tagStrings}}`
  }

  return ''
}

function formatDistance(meters) {
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

function getCalmnessDescription(type) {
  switch (type) {
    case 'path': return 'Off-street bike paths (very calm)'
    case 'street': return 'Mellow streets (calm)'
    case 'route': return 'Main streets, often with bike lanes (less calm)'
    default: return 'Not calm'
  }
}

function getLightColor(hexColor) {
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
