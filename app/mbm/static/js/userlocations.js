import { getUserLocations, saveUserLocations } from './storage.js'

// TODO:
// Differentiate icons
// Require unique names
// Make sure we don't cover saved location marker with source or target marker
// Add locations to autocomplete

// Allows users to create markers for their own locations on the map by double-clicking
// These locations are saved and loaded from localstorage
export default class UserLocations {
    constructor(mbm) {
        this.mbm = mbm
        this.map = mbm.map
        this.addLocationPopup = L.popup()

        // Disable double click zooming so we can use that gesture for adding a new location
        this.map.doubleClickZoom.disable()
        this.map.on('dblclick', this.showAddLocationPopup.bind(this))

        // Load user locations from localstorage
        this.locations = getUserLocations() || {}

        // Render user locations
        for (const [name, location] of Object.entries(this.locations)) {
            this.renderSavedLocation(name, location)
        }
    }

    // Create a popup with a form for users to save a new location to the map
    showAddLocationPopup(clickEvent) {
        const $form = $(`
            <form>
                <h4>Add new saved location?</h4>
                <label for="locationName">Name</label>
            </form>`)
        const $nameInput = $('<input id="locationName" name="locationName">')
        const $saveButton = $('<button class="btn btn-primary btn-block">Save location</button>')
        $form.append($nameInput).append($saveButton)

        $form.submit((submitEvent) => {
            submitEvent.preventDefault()

            const name = $nameInput.val()
            this.addLocation(name, clickEvent.latlng.lat, clickEvent.latlng.lng)

            this.closeAddLocationPopup()
        })
    
        this.addLocationPopup
            .setLatLng(clickEvent.latlng)
            .setContent($form[0])
            .openOn(this.map)
        }
        
    // Close the new location popup
    closeAddLocationPopup() {
        this.map.closePopup(this.addLocationPopup)
    }

    // Add a new location to the map and update the locations in localstorage
    addLocation(name, lat, lng) {
        location = {lat, lng}
        this.locations[name] = location
        this.renderSavedLocation(name, location)
        this.saveLocations()
    }

    // Save user locations to local storage
    saveLocations() {
        saveUserLocations(this.locations)
    }

    //"render" a location to the map:
    //  - Add a marker to the map at that location
    //  - Add navigation buttons to marker popup
    //  - Add button to marker for deleting location
    //  - 
    renderSavedLocation(name, location) {
        const marker = L.marker([location.lat, location.lng], {
            title: name,
            zIndexOffset: 100,
        })

        const popup = L.popup()
        const sourceButton = $(`<button class="btn btn-primary btn-block">Directions from ${name}</button>`).click(() => {
            this.mbm.setSourceLocation(location.lat, location.lng, name)
            this.map.closePopup(popup)
        })
        const targetButton = $(`<button class="btn btn-primary btn-block">Directions to ${name}</button>`).click(() => {
            this.mbm.setTargetLocation(location.lat, location.lng, name)
            this.map.closePopup(popup)
        })
        const removeButton = $(`<button class="btn btn-danger btn-block">Remove ${name} from saved locations</button>`).click(() => {
            this.removeLocation(name)
        })
        const $content = $(`<div><h4 class="text-center">${name}</h4></div>`)
        $content.append(sourceButton).append(targetButton).append(removeButton)
        popup.setContent($content[0])

        marker.bindPopup(popup)
        this.mbm.addMarker(name, marker)
  }

    removeLocation(name) {
        delete this.locations[name]
        this.mbm.removeMarker(name)
        this.saveLocations()
    }

}
