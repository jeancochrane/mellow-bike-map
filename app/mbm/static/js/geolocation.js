// Manages geolocation related functionality for the app
//
// TODO: store the result of `watchPosition()` and remove the handler when we 
// don't need the user's location
export default class Geolocation {
  constructor(app) {
    this.app = app
    // Since the app doesn't yet have any central state management, this string is used
    // across multiple modules to indicate that a location should be based on the user's
    // GPS position
    this.gpsLocationString = app.gpsLocationString
    this.startGPSTracking()
  }

  startGPSTracking() {
    if (navigator.geolocation) {
      navigator.geolocation.watchPosition(this.handleGPSPositionUpdate.bind(this))
    }
  }

  // Continuously update marker as position changes when the user selects the
  // GPS location option for the navigation source or target
  handleGPSPositionUpdate(position) {
    for (const [name, { input }] of Object.entries(this.app.directionsFormElements)) {
      // Only update the source marker if the user is using their current location
      // as the source location
      if (input.value != this.gpsLocationString) {
        continue
      }
      this.app.setMarkerLocation(name, position.coords.latitude, position.coords.longitude, this.gpsLocationString)
      this.app.zoomToLocation(position.coords.latitude, position.coords.longitude)
    }
  }

  // Request the users location from the browser and run our handleGPSPositionUpdate method
  // Since we're already using watchPosition to get updates, this is mainly used to trigger our
  // handler, and as such, we don't mind receiving a cached value for the user location. This is
  // important, because getCurrentPosition can sometimes take tens of seconds to return a response.
  triggerGPSPositionUpdate() {
    if (navigator.geolocation) {
      const options = {
        enableHighAccuracy: true,
        timeout: 5000,
        maximumAge: Infinity
      }
      navigator.geolocation.getCurrentPosition(
        this.handleGPSPositionUpdate.bind(this),
        (err) => console.log(`Error retrieving GPS position. error code ${err.code}: ${err.message}`),
        options
      )
    }
  }
}
