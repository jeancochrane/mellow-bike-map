// This should probably all be moved to python but is a first draft of
// what turn-by-turn directions will look like

const headingToEnglishManeuver = (heading, previousHeading) => {
  const maneuvers = {
    0: { maneuver: "Continue", cardinal: "North" },
    45: { maneuver: "Turn slightly to the right", cardinal: "Northeast" },
    90: { maneuver: "Turn right", cardinal: "East" },
    135: { maneuver: "Take a sharp right turn", cardinal: "Southeast" },
    180: { maneuver: "Turn around", cardinal: "South" },
    225: { maneuver: "Take a sharp left turn", cardinal: "Southwest" },
    270: { maneuver: "Turn left", cardinal: "West" },
    315: { maneuver: "Turn slightly to the left", cardinal: "Northwest" },
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
    const direction = { name, distance, maneuver, heading, cardinal }
    console.log({previousHeading, previousName, ...direction})

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
    }

    previousHeading = heading
    previousName = name
  }
  return directions
}

const serializeDirections = (directions) => {
  const lines = []
  const first = directions.shift()
  lines.push(`Head ${first.cardinal} on ${first.name || 'an unknown street'} for ${Math.round(first.distance)} meters`)
  for (const direction of directions) {
    lines.push(`${direction.maneuver} onto ${direction.name || 'an unknown street'} and head ${direction.cardinal} for ${Math.round(direction.distance)} meters`)
  }
  // TODO: add which side of the street it's on
  lines[lines.length - 1] += " until you reach your destination"

  return lines
}

export { serializeDirections, directionsList }
