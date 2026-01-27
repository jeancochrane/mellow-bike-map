export function displayDirections(app, directions) {
  const $directionsList = $('#directions-list')

  // Clear any existing directions
  $directionsList.empty()

  // Process and add each direction
  directions.forEach((direction, index) => {
    // Determine maneuver for first direction
    const maneuver = index === 0 ? 'Continue' : direction.maneuver

    // Get the color based on the type
    const color = app.getLineColor(direction.type)

    // Get the icon with the appropriate color
    const icon = getDirectionIcon(maneuver, color)

    // Direction text is computed server-side for consistency
    const directionText = direction.directionText || ''

    // Build the list item with clickable class and color data
    let listItemHtml = `<li class="direction-item" data-direction-index="${index}" data-color="${color}"><span class="direction-icon-wrapper">${icon}</span><span class="direction-text">${directionText}`

    listItemHtml += `</span></li>`

    $directionsList.append(listItemHtml)
  })

  // Add click handlers to each direction item
  $('.direction-item').on('click', (e) => {
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
