// This should probably all be moved to python but is a first draft of
// what turn-by-turn directions will look like

const headingToEnglishManeuver = (heading, previousHeading) => {
  const maneuvers = {
    0: { maneuver: "Continue", cardinal: "north" },
    45: { maneuver: "Turn slightly to the right", cardinal: "northeast" },
    90: { maneuver: "Turn right", cardinal: "east" },
    135: { maneuver: "Take a sharp right turn", cardinal: "southeast" },
    180: { maneuver: "Turn around", cardinal: "south" },
    225: { maneuver: "Take a sharp left turn", cardinal: "southwest" },
    270: { maneuver: "Turn left", cardinal: "west" },
    315: { maneuver: "Turn slightly to the left", cardinal: "northwest" },
  }

  const nearest45 = (x) => (Math.round(x / 45) * 45) % 360

  const angle = nearest45(((heading - previousHeading) + 360) % 360)

  return { maneuver: maneuvers[angle]?.maneuver, cardinal: maneuvers[nearest45(heading)].cardinal }
}

const directionsList = (features) => {
  const directions = []
  let previousHeading, previousName
  for (const feature of features) {
    const name = feature.properties.name
    const heading = feature.properties.heading
    const { maneuver, cardinal } = headingToEnglishManeuver(heading, previousHeading)
    const distance = feature.properties.distance
    // Include OSM debugging data
    const osmData = {
      osm_id: feature.properties.osm_id,
      tag_id: feature.properties.tag_id,
      oneway: feature.properties.oneway,
      rule: feature.properties.rule,
      priority: feature.properties.priority,
      maxspeed_forward: feature.properties.maxspeed_forward,
      maxspeed_backward: feature.properties.maxspeed_backward,
      osm_tags: feature.properties.osm_tags
    }
    const direction = { name, distance, maneuver, heading, cardinal, osmData }

    // If the street name changed or there's a turn to be made, add a new direction to the list
    const streetNameChanged = previousName && name !== previousName
    const turnRequired = (maneuver !== 'Continue' || !previousHeading) // "Continue"
    if (streetNameChanged || turnRequired) {
      directions.push(direction)
    }
    // Otherwise this is just a quirk of our data and the line segments should be combined
    else {
      if (directions.length) {
        directions[directions.length - 1].distance += distance
      }
      // Sometimes only some segments of a street are named, so check if the
      // previous segment is named and backfill the name if not
      if (name && directions.length && !directions[directions.length - 1].name) {
        directions[directions.length - 1].name = name
      }
      // For unnamed streets, preserve OSM data from the current segment if previous doesn't have a name
      if (!name && osmData && directions.length && !directions[directions.length - 1].name) {
        directions[directions.length - 1].osmData = osmData
      }
    }

    previousHeading = heading
    previousName = name
  }
  return directions
}

const formatOsmDebugInfo = (osmData) => {
  if (!osmData) return ''
  
  const parts = []
  parts.push(`[OSM ID: ${osmData.osm_id}`)
  if (osmData.tag_id) parts.push(`Tag ID: ${osmData.tag_id}`)
  if (osmData.oneway && osmData.oneway !== 'NO') parts.push(`Oneway: ${osmData.oneway}`)
  if (osmData.rule) parts.push(`Rule: ${osmData.rule}`)
  if (osmData.priority) parts.push(`Priority: ${osmData.priority}`)
  if (osmData.maxspeed_forward) parts.push(`Max Speed Fwd: ${osmData.maxspeed_forward}`)
  if (osmData.maxspeed_backward) parts.push(`Max Speed Back: ${osmData.maxspeed_backward}`)
  
  // Add OSM tags if available
  if (osmData.osm_tags && Object.keys(osmData.osm_tags).length > 0) {
    const tagStrings = Object.entries(osmData.osm_tags)
      .map(([key, value]) => `${key}=${value}`)
      .join(', ')
    parts.push(`Tags: {${tagStrings}}`)
  }
  
  return parts.join(', ') + ']'
}

const serializeDirections = (directions) => {
  const lines = []
  
  // Handle empty directions array
  if (!directions || directions.length === 0) {
    return lines
  }
  
  const first = directions.shift()
  let firstStreetName = first.name || 'an unknown street'
  // Add OSM debug info for unnamed streets
  if (!first.name && first.osmData) {
    firstStreetName += ' ' + formatOsmDebugInfo(first.osmData)
  }
  lines.push(`Head ${first.cardinal} on ${firstStreetName} for ${Math.round(first.distance)} meters`)
  
  for (const direction of directions) {
    let streetName = direction.name || 'an unknown street'
    // Add OSM debug info for unnamed streets
    if (!direction.name && direction.osmData) {
      streetName += ' ' + formatOsmDebugInfo(direction.osmData)
    }
    lines.push(`${direction.maneuver} onto ${streetName} and head ${direction.cardinal} for ${Math.round(direction.distance)} meters`)
  }
  // TODO: add which side of the street it's on
  lines[lines.length - 1] += " until you reach your destination"

  return lines
}

export { serializeDirections, directionsList }
