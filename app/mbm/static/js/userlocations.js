import { getUserLocations, saveUserLocations } from './storage.js'

// TODO:
//   - Add some different icon styles to differentiate target, dest, saved locations, and GPS position
//   - Require unique names for locations
//   - Add locations to autocomplete

// Allows users to create markers for their own locations on the map by double-clicking
// These locations are saved and loaded from localstorage
export default class UserLocations {
    constructor(app) {
        this.app = app
        this.map = app.map

        this.form = null
        this.addLocationPopup = this.createLocationPopup()

        // Disable double click zooming so we can use that gesture for adding a new location
        this.map.doubleClickZoom.disable()

        // Store the bound handler so we can remove it during unmount
        this.dblclickHandler = this.showAddLocationPopup.bind(this)
        this.map.on('dblclick', this.dblclickHandler)

        // Load user locations from localstorage
        this.locations = getUserLocations() || {}

        // Render user locations
        for (const [name, location] of Object.entries(this.locations)) {
            this.renderSavedLocation(name, location)
        }
    }

    createLocationPopup() {
        const popup = L.popup()
        const $form = $(`
            <form>
                <h4>Add new saved location?</h4>
                <label for="locationName">Name</label>
            </form>`
        )
        const $nameInput = $('<input id="locationName" name="locationName">')
        this.$nameInput = $nameInput
        const $saveButton = $('<button class="btn btn-primary btn-block">Save location</button>')
        $form.append($nameInput).append($saveButton)
        $form.submit(this.handleFormSubmission.bind(this))

        this.form = $form[0]
        popup.setContent(this.form)
        return popup
    }

    handleFormSubmission(event) {
        event.preventDefault()

        const name = this.$nameInput.val()
        const latlng = this.addLocationPopup.getLatLng()

        this.addLocation(name, latlng.lat, latlng.lng)
        this.form.reset()
        this.closeAddLocationPopup()
    }

    // Create a popup with a form for users to save a new location to the map
    showAddLocationPopup(clickEvent) {
        this.addLocationPopup
            .setLatLng(clickEvent.latlng)
            .openOn(this.map)
    }

    // Close the new location popup
    closeAddLocationPopup() {
        this.map.closePopup(this.addLocationPopup)
    }

    // Add a new location to the map and update the locations in localstorage
    addLocation(name, lat, lng) {
        const location = { lat, lng }
        this.locations[name] = location
        this.renderSavedLocation(name, location)
        this.saveLocations()
    }

    // Save user locations to local storage
    saveLocations() {
        saveUserLocations(this.locations)
    }

    // "render" a location to the map by creating a marker at that location,
    // with a popup containing controls to navigate to/from that marker or to
    // delete it
    renderSavedLocation(name, location) {
        const marker = L.marker([location.lat, location.lng], {
            title: name,
            // Make sure these markers sit above the regular source/target markers
            zIndexOffset: 100,
        })

        const popup = L.popup()
        const sourceButton = $(`<button class="btn btn-primary btn-block">Directions from ${name}</button>`).click(() => {
            this.app.setSourceLocation(location.lat, location.lng, name)
            this.map.closePopup(popup)
        })
        const targetButton = $(`<button class="btn btn-primary btn-block">Directions to ${name}</button>`).click(() => {
            this.app.setTargetLocation(location.lat, location.lng, name)
            this.map.closePopup(popup)
        })
        const removeButton = $(`<button class="btn btn-danger btn-block">Remove ${name} from saved locations</button>`).click(() => {
            this.removeLocation(name)
        })
        const $content = $(`<div><h4 class="text-center">${name}</h4></div>`)
        $content.append(sourceButton).append(targetButton).append(removeButton)
        popup.setContent($content[0])

        marker.bindPopup(popup)
        this.app.addMarker(name, marker)
    }

    // Remove a location from the map and delete it from storage
    removeLocation(name) {
        delete this.locations[name]
        this.app.removeMarker(name)
        this.saveLocations()
    }

    unmount() {
        this.map.doubleClickZoom.enable()
        this.map.off('dblclick', this.dblclickHandler)

        for (const markerName of Object.keys(this.locations)) {
            this.app.removeMarker(markerName)
        }
    }
}
