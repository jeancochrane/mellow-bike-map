-- Label parks in the chicago_ways table
-- Parks are defined as: chicago_ways that intersect with Chicago park boundaries

\echo ''
\echo '========================================='
\echo 'Starting Park Labeling Process'
\echo '========================================='
\echo ''

-- Add columns if they don't exist
\echo '[Step 1/6] Adding database columns...'
ALTER TABLE chicago_parks ADD COLUMN IF NOT EXISTS humanized_name TEXT;
ALTER TABLE chicago_ways ADD COLUMN IF NOT EXISTS park_name TEXT;

\echo '[Step 2/6] Creating spatial index on chicago_parks...'
CREATE INDEX IF NOT EXISTS chicago_parks_geom_idx ON chicago_parks USING GIST(wkb_geometry);

\echo '[Step 3/6] Computing humanized park names...'
-- Humanize park names: remove text in parens, title case, add " Park" to the end if not already present
-- Will be present for park names like "PARK NO. 399", will not be for the majority of parks, like "MAPLEWOOD"
UPDATE chicago_parks
SET humanized_name = CASE 
    WHEN UPPER(TRIM(REGEXP_REPLACE(park, '\s*\([^)]*\)', '', 'g'))) LIKE '%PARK%' 
    THEN INITCAP(TRIM(REGEXP_REPLACE(park, '\s*\([^)]*\)', '', 'g')))
    ELSE INITCAP(TRIM(REGEXP_REPLACE(park, '\s*\([^)]*\)', '', 'g'))) || ' Park'
END
WHERE park IS NOT NULL AND park != '';

\echo '[Step 4/6] Identifying chicago_ways within park boundaries...'
\echo '  This step may take several minutes depending on data size...'

-- Update chicago_ways with pre-computed humanized park names where they intersect park boundaries
UPDATE chicago_ways 
SET park_name = chicago_parks.humanized_name
FROM chicago_parks
WHERE ST_Intersects(chicago_ways.the_geom, chicago_parks.wkb_geometry)
  AND chicago_parks.humanized_name IS NOT NULL;

\echo '  ✓ Analysis complete'

\echo '[Step 5/6] Creating index on park_name column...'
CREATE INDEX IF NOT EXISTS chicago_ways_park_name_idx ON chicago_ways(park_name) WHERE park_name IS NOT NULL;

\echo '[Step 6/6] Reporting statistics...'

\echo ''
\echo '========================================='
\echo 'Park Labeling Complete!'
\echo '========================================='
\echo ''

-- Report statistics
SELECT 
    COUNT(*) FILTER (WHERE park_name IS NOT NULL) as ways_in_parks,
    COUNT(*) FILTER (WHERE park_name IS NULL) as ways_outside_parks,
    COUNT(*) as total_ways,
    ROUND(100.0 * COUNT(*) FILTER (WHERE park_name IS NOT NULL) / COUNT(*), 2) as park_percentage
FROM chicago_ways;

\echo ''
\echo 'Top 10 parks by number of chicago_ways:'
SELECT 
    park_name,
    COUNT(*) as way_count
FROM chicago_ways
WHERE park_name IS NOT NULL
GROUP BY park_name
ORDER BY way_count DESC
LIMIT 10;

