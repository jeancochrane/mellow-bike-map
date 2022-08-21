// Functions for saving and loading data from localStorage

const locationsKey = 'savedLocations'
const preferencesKey = 'preferences'

const getUserLocations = () => {
    const locations = JSON.parse(localStorage.getItem(locationsKey))
    return locations
}

const saveUserLocations = (locations) => {
    localStorage.setItem(locationsKey, JSON.stringify(locations))
}

const getUserPreferences = () => {
    const preferences = JSON.parse(localStorage.getItem(preferencesKey))
    return preferences
}

const saveUserPreferences = (preferences) => {
    localStorage.setItem(JSON.stringify(preferences))
}

export { getUserLocations, saveUserLocations, getUserPreferences, saveUserPreferences }
