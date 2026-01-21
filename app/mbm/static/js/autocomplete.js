// Address components for autocomplete
const canonicalComponents = [
  ['street_number', 'short_name', ' '],
  ['route', 'long_name', ', '],
  ['locality', 'long_name', ', '],
  ['administrative_area_level_1', 'short_name', ' '],
  ['postal_code', 'short_name', '']
]


const initAutocomplete = (inputElement, markerName, app) => {
  // Define bounds for Chicagoland
  const chicagoBounds = new google.maps.LatLngBounds(
    new google.maps.LatLng(41.45, -88.3),
    new google.maps.LatLng(42.2, -87.3)
  )

  // Create the autocomplete object with Chicagoland bounds and strict bounds enforcement
  let autocomplete = new google.maps.places.Autocomplete(
    inputElement, {
      componentRestrictions: { country: "us" },
      bounds: chicagoBounds,
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

    // If we've set the location ourselves (via GPS or a user saved location),
    // then the value of place will just be {name: inputElement.value}
    if (!place.geometry) {
      return
    }

    const lat = place.geometry.location.lat()
    const lng = place.geometry.location.lng()

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
    app.setSourceOrTargetLocation(markerName, lat, lng, addressString)
  });

  // TODO: This doesn't really need to depend on geolocation. We want to suggest
  // results all over the city regardless of where the user is located, so we could
  // instead hardcode a bounds object for chicago city limits. As a bonus, we could
  // then set the autocomplete to use strictbounds and only return results within
  // them rather than just biasing towards those results. Alternatively, we could
  // have the backend generate these bounds based on where it has route definitions.
  //
  // Bias the autocomplete object to the user's geographical location,
  // as supplied by the browser's 'navigator.geolocation' object.
  if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(position => {
      const geolocation = {
        lat: position.coords.latitude,
        lng: position.coords.longitude
      }
      app.geolocation.handleGPSPositionUpdate(position)
      const circle = new google.maps.Circle({
        center: geolocation,
        // This is 1500 meters for me. Do we really want to bias the autocomplete to locations within 1500 meters?
        radius: position.coords.accuracy
      })
      autocomplete.setBounds(circle.getBounds())
    })
  }
  return autocomplete
}


// This is a very overcomplicated way to put our own items into the
// autocomplete comboboxes. There doesn't seem to be any official way to do this
// other than completely implementing the autocomplete widget yourself, thus our hacks.
// Right now this is only used for a user to select their location.
//
// TODO:
//  - Add user's saved locations to the list and filter them by user input
//  - Open the dropdown as soon as input is focused (like they do on https://citymapper.com/webapp)
//  - Allow user to select our options with the keyboard (rn you can only do it with a mouse click or tap)
//
const addCustomOption = (app, optionText, callback) => {

  // The google autocomplete container doesn't have any obvious way to find the
  // input associated with the list of options, which makes it difficult to write
  // a handler for a user selecting one of our preset options (which input
  // element should we update?). So instead, we keep track of which input element
  // received a focus event most recently and update it when a custom option is selected
  let markerName
  const recordFocusEvent = (event) => {
    markerName = event.target.id
  }

  app.directionsFormElements.source.input.addEventListener('focus', recordFocusEvent)
  app.directionsFormElements.target.input.addEventListener('focus', recordFocusEvent)

  const ourOption = $(`
    <div class="pac-item" tabindex="0">
      <span class="pac-icon pac-icon-marker"></span>
      <span class="pac-item-query">${optionText}</span>
    </div>
  `).on('mousedown', () => {
    app.directionsFormElements[markerName].input.value = optionText
    callback(markerName)
  })
  $('.pac-container').append(ourOption)

  // Watch the body element for the addition of new child nodes. Once the
  // autocomplete containers are present, append our options to the list,
  // then remove the observer.
  const observer = new MutationObserver((mutations, observer) => {
    // Add our preset locations to the list
    const autocompleteContainers = $('.pac-container')
    if (autocompleteContainers.length == 2) {
      autocompleteContainers.append(ourOption)
      observer.disconnect()
    }
  })

  observer.observe(document.body, {
    childList: true
  })
}

export default { initAutocomplete, addCustomOption }
