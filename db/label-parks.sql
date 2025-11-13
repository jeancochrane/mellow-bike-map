-- Label parks in the chicago_ways table
-- Parks are defined as: chicago_ways that intersect with Chicago park boundaries

\echo ''
\echo '========================================='
\echo 'Starting Park Labeling Process'
\echo '========================================='
\echo ''

-- Add column if it doesn't exist
\echo '[Step 1/5] Adding database column...'
ALTER TABLE chicago_ways ADD COLUMN IF NOT EXISTS park_name TEXT;

\echo '[Step 2/5] Creating spatial index on chicago_parks...'
CREATE INDEX IF NOT EXISTS chicago_parks_geom_idx ON chicago_parks USING GIST(wkb_geometry);

\echo '[Step 3/5] Identifying chicago_ways within park boundaries...'
\echo '  This step may take several minutes depending on data size...'

-- Update chicago_ways with park names where they intersect park boundaries
-- Humanize park names: remove text in parens, title case, add " Park"
UPDATE chicago_ways 
SET park_name = parks.humanized_name
FROM (
    SELECT 
        cp.park,
        cp.wkb_geometry,
        -- Remove everything in parentheses, convert to title case, and add " Park" to the end of the name if not already present. Will be present for park names like "PARK NO. 399", will not be for the majority of parks, like "MAPLEWOOD".
        CASE 
            WHEN UPPER(TRIM(REGEXP_REPLACE(cp.park, '\s*\([^)]*\)', '', 'g'))) LIKE '%PARK%' 
            THEN INITCAP(TRIM(REGEXP_REPLACE(cp.park, '\s*\([^)]*\)', '', 'g')))
            ELSE INITCAP(TRIM(REGEXP_REPLACE(cp.park, '\s*\([^)]*\)', '', 'g'))) || ' Park'
        END as humanized_name
    FROM chicago_parks cp
    WHERE cp.park IS NOT NULL AND cp.park != ''
) AS parks
WHERE ST_Intersects(chicago_ways.the_geom, parks.wkb_geometry);

\echo '  ✓ Analysis complete'

\echo '[Step 4/5] Creating index on park_name column...'
CREATE INDEX IF NOT EXISTS chicago_ways_park_name_idx ON chicago_ways(park_name) WHERE park_name IS NOT NULL;

\echo '[Step 5/5] Reporting statistics...'

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

