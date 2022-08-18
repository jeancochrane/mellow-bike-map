// Address components for autocomplete
const canonicalComponents = [
    ['street_number', 'short_name', ' '],
    ['route', 'long_name', ', '],
    ['locality', 'long_name', ', '],
    ['administrative_area_level_1', 'short_name', ' '],
    ['postal_code', 'short_name', '']
]


const initAutocomplete = (inputElement, markerName, mbm) => {
    // Create the autocomplete object
    let autocomplete = new google.maps.places.Autocomplete(
      inputElement, { componentRestrictions: { country: "us" } }
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
      mbm.setMarkerLocation(markerName, lat, lng, addressString)
    });

    // Bias the autocomplete object to the user's geographical location,
    // as supplied by the browser's 'navigator.geolocation' object.
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(position => {
        const geolocation = {
          lat: position.coords.latitude,
          lng: position.coords.longitude
        }
        mbm.handleGPSPositionUpdate(position)
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

export {initAutocomplete}
