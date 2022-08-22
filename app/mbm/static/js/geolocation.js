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
}
