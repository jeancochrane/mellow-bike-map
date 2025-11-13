// This should probably all be moved to python but is a first draft of
// what turn-by-turn directions will look like

const describeUnnamedStreet = (osmTags, parkName) => {
  if (!osmTags) return 'an unknown street'
  
  let description = ''
  
  if (osmTags.highway === 'service' && osmTags.service === 'alley') {
    description = 'an alley'
  } else if (osmTags.highway === 'service') {
    description = 'an access road'
  } else if (osmTags.footway === 'crossing') {
    description = 'a crosswalk'
  } else if (osmTags.highway === 'footway' && osmTags.footway === 'sidewalk') {
    description = 'a sidewalk'
  } else if (parkName) {
    // If inside a park and no specific description, call it a path
    description = 'a path'
  } else {
    description = 'an unknown street'
  }
  
  // Add park name if the street is within a park
  if (parkName) {
    description += ` inside ${parkName}`
  }
  
  return description
}

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
  let previousHeading, previousEffectiveName
  for (let i = 0; i < features.length; i++) {
    const feature = features[i]
    const name = feature.properties.name
    const heading = feature.properties.heading
    const { maneuver, cardinal } = headingToEnglishManeuver(heading, previousHeading)
    const distance = feature.properties.distance
    const type = feature.properties.type
    // Include OSM debugging data
    const osmData = {
      osm_id: feature.properties.osm_id,
      tag_id: feature.properties.tag_id,
      oneway: feature.properties.oneway,
      rule: feature.properties.rule,
      priority: feature.properties.priority,
      maxspeed_forward: feature.properties.maxspeed_forward,
      maxspeed_backward: feature.properties.maxspeed_backward,
      length_m: feature.properties.distance,
      osm_tags: feature.properties.osm_tags,
      park_name: feature.properties.park_name
    }
    // Create chicago_way object with instruction info
    const chicagoWay = {
      osmData,
      maneuver,
      cardinal,
      distance,
      name
    }
    const direction = { name, distance, maneuver, heading, cardinal, type, osmData, osmDataChicagoWays: [chicagoWay], featureIndices: [i] }

    const effectiveName = name || describeUnnamedStreet(osmData.osm_tags, osmData.park_name)

    // Determine if this is a slight turn that can be collapsed
    const isSlightTurn = (maneuver === 'Turn slightly to the left' || maneuver === 'Turn slightly to the right')
    const sameNamedStreet = effectiveName === previousEffectiveName
    const isNamedStreet = !!name  // Only collapse slight turns for actual named streets
    const shouldCollapseSlightTurn = isSlightTurn && sameNamedStreet && isNamedStreet
    
    // If the street name changed or there's a turn to be made, add a new direction to the list
    // Exception: collapse slight turns on the same named street
    const streetNameChanged = previousEffectiveName && effectiveName !== previousEffectiveName
    const turnRequired = (maneuver !== 'Continue' || !previousHeading) // "Continue"
    if ((streetNameChanged || turnRequired) && !shouldCollapseSlightTurn) {
      directions.push(direction)
    }
    // Otherwise this is just a quirk of our data and the line segments should be combined
    else {
      if (directions.length) {
        directions[directions.length - 1].distance += distance
        // Add this chicago_way's data to the array
        directions[directions.length - 1].osmDataChicagoWays.push(chicagoWay)
        // Track the feature index
        directions[directions.length - 1].featureIndices.push(i)
      }
      // Sometimes only some chicago_ways of a street are named, so check if the
      // previous chicago_way is named and backfill the name if not
      if (name && directions.length && !directions[directions.length - 1].name) {
        directions[directions.length - 1].name = name
      }
      // For unnamed streets, preserve OSM data from the current chicago_way if previous doesn't have a name
      if (!name && osmData && directions.length && !directions[directions.length - 1].name) {
        directions[directions.length - 1].osmData = osmData
      }
    }

    previousHeading = heading
    previousEffectiveName = effectiveName
  }
  return directions
}

const formatOsmDebugInfo = (osmData) => {
  if (!osmData) return ''
  
  const parts = []
  parts.push(`[OSM ID: ${osmData.osm_id}`)
  if (osmData.tag_id) parts.push(`Tag ID: ${osmData.tag_id}`)
  if (osmData.park_name) parts.push(`Park: ${osmData.park_name}`)
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
  let firstStreetName = first.name || describeUnnamedStreet(first.osmData?.osm_tags, first.osmData?.park_name)
  // Add OSM debug info for unnamed streets
  if (!first.name && first.osmData) {
    firstStreetName += ' ' + formatOsmDebugInfo(first.osmData)
  }
  lines.push(`Head ${first.cardinal} on ${firstStreetName} for ${Math.round(first.distance)} meters`)
  
  for (const direction of directions) {
    let streetName = direction.name || describeUnnamedStreet(direction.osmData?.osm_tags, direction.osmData?.park_name)
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

export { serializeDirections, directionsList, describeUnnamedStreet }
