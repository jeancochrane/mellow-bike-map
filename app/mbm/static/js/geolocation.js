// Manages geolocation related functionality for the app
//
// TODO: store the result of `watchPosition()` and remove the handler when we 
// don't need the user's location
export default class Geolocation {
  constructor(app) {
    this.app = app
    this.markerName = 'gpslocation'
    this.startGPSTracking()
  }

  startGPSTracking() {
    if (navigator.geolocation) {
      navigator.geolocation.watchPosition(this.handleGPSPositionUpdate.bind(this))
    }
  }

  createMarker(lat, long) {
    const marker = L.marker([lat, long])
    const icon = L.divIcon({className: 'gps-location-marker-icon'})
    marker.setIcon(icon)
    marker.bindPopup(this.app.gpsLocationString)
    this.app.addMarker(this.markerName, marker)
    return marker
  }

  // Continuously update marker as position changes when the user selects the
  // GPS location option for the navigation source or target
  handleGPSPositionUpdate(position) {
    if (!this.marker) {
      this.marker = this.createMarker(position.coords.latitude, position.coords.longitude)
    } else {
      this.app.setMarkerLocation(this.markerName, position.coords.latitude, position.coords.longitude)
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
