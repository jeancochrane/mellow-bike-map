const locationsKey = 'savedLocations'

const getUserLocations = () => {
    // fetch from local storage
    const locations = JSON.parse(localStorage.getItem(locationsKey))
    return locations
}

const saveUserLocations = (locations) => {
    localStorage.setItem(locationsKey, JSON.stringify(locations))
}

export {getUserLocations, saveUserLocations}
