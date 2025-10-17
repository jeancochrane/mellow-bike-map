-- Label alleys in the chicago_ways table
-- Alleys are defined as:
-- 1. No name
-- 2. Parallel to named roads (within 15 degrees)
-- 3. Closer than 50 feet (15.24 meters) from named roads
-- 4. Run for at least 100 feet (30.48 meters)

\echo ''
\echo '========================================='
\echo 'Starting Alley Labeling Process'
\echo '========================================='
\echo ''

-- Add columns if they don't exist
\echo '[Step 1/7] Adding database columns...'
ALTER TABLE chicago_ways ADD COLUMN IF NOT EXISTS is_alley BOOLEAN DEFAULT FALSE;
ALTER TABLE chicago_ways ADD COLUMN IF NOT EXISTS bearing FLOAT;

\echo '[Step 2/7] Creating helper functions...'

-- Create a function to calculate the bearing (azimuth) of a line
-- Returns bearing in degrees (0-360)
CREATE OR REPLACE FUNCTION line_bearing(geom geometry) 
RETURNS float AS $$
DECLARE
    start_point geometry;
    end_point geometry;
    azimuth float;
BEGIN
    start_point := ST_StartPoint(geom);
    end_point := ST_EndPoint(geom);
    azimuth := ST_Azimuth(start_point, end_point);
    
    -- Handle NULL case (start and end are the same)
    IF azimuth IS NULL THEN
        RETURN NULL;
    END IF;
    
    RETURN degrees(azimuth);
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Create a function to check if two bearings are parallel (within tolerance)
-- Handles the 0/360 degree wraparound
CREATE OR REPLACE FUNCTION bearings_parallel(bearing1 float, bearing2 float, tolerance float DEFAULT 15.0)
RETURNS boolean AS $$
DECLARE
    diff float;
    normalized_diff float;
BEGIN
    -- Handle NULL cases
    IF bearing1 IS NULL OR bearing2 IS NULL THEN
        RETURN FALSE;
    END IF;
    
    -- Calculate absolute difference
    diff := abs(bearing1 - bearing2);
    
    -- Normalize to handle wraparound (e.g., 5 degrees and 355 degrees are 10 degrees apart)
    IF diff > 180 THEN
        normalized_diff := 360 - diff;
    ELSE
        normalized_diff := diff;
    END IF;
    
    -- Check if parallel (within tolerance) or opposite direction
    -- Allow for both parallel directions (0° tolerance or 180° ± tolerance)
    RETURN normalized_diff <= tolerance OR abs(normalized_diff - 180) <= tolerance;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Pre-compute bearings for all ways
\echo '[Step 3/7] Computing bearings for all ways...'
UPDATE chicago_ways 
SET bearing = line_bearing(the_geom);

\echo '  ✓ Bearings computed'
SELECT '  → Found ' || COUNT(*) || ' ways with valid bearings' as status FROM chicago_ways WHERE bearing IS NOT NULL;

\echo '[Step 4/7] Creating indexes...'
CREATE INDEX IF NOT EXISTS chicago_ways_bearing_idx ON chicago_ways(bearing) WHERE bearing IS NOT NULL;

\echo '[Step 5/7] Identifying candidate alleys (unnamed, ≥100ft)...'

-- Create a temporary table of candidate alleys (unnamed, at least 100 feet long)
CREATE TEMP TABLE candidate_alleys AS
SELECT 
    gid,
    the_geom,
    bearing,
    ST_Transform(the_geom, 3857) as geom_meters
FROM chicago_ways
WHERE 
    (name IS NULL OR name = '')
    AND ST_Length(ST_Transform(the_geom, 3857)) >= 30.48  -- At least 100 feet
    AND bearing IS NOT NULL;

SELECT '  → Found ' || COUNT(*) || ' candidate alleys' as status FROM candidate_alleys;

\echo '  Creating indexes on candidate alleys...'
CREATE TEMP TABLE named_roads AS
SELECT 
    gid,
    the_geom,
    bearing,
    ST_Transform(the_geom, 3857) as geom_meters
FROM chicago_ways
WHERE 
    name IS NOT NULL 
    AND name != ''
    AND bearing IS NOT NULL;

SELECT '  → Found ' || COUNT(*) || ' named roads' as status FROM named_roads;

\echo '  Building spatial indexes (this improves performance)...'
CREATE INDEX candidate_alleys_geom_idx ON candidate_alleys USING GIST(geom_meters);
CREATE INDEX named_roads_geom_idx ON named_roads USING GIST(geom_meters);

\echo '[Step 6/7] Analyzing spatial relationships (parallel + within 50ft)...'
\echo '  This step may take several minutes depending on data size...'

-- Mark alleys: unnamed ways that are parallel to and within 50 feet of a named road
UPDATE chicago_ways 
SET is_alley = TRUE
WHERE gid IN (
    SELECT DISTINCT c.gid
    FROM candidate_alleys c
    WHERE EXISTS (
        SELECT 1
        FROM named_roads n
        WHERE 
            -- Within 50 feet (15.24 meters)
            ST_DWithin(c.geom_meters, n.geom_meters, 15.24)
            -- Parallel check: bearings within 15 degrees
            AND bearings_parallel(c.bearing, n.bearing, 15.0)
        LIMIT 1
    )
);

\echo '  ✓ Analysis complete'

\echo '[Step 7/7] Creating final indexes...'
CREATE INDEX IF NOT EXISTS chicago_ways_is_alley_idx ON chicago_ways(is_alley);

\echo ''
\echo '========================================='
\echo 'Alley Labeling Complete!'
\echo '========================================='
\echo ''

-- Report statistics
SELECT 
    COUNT(*) FILTER (WHERE is_alley = TRUE) as alley_count,
    COUNT(*) FILTER (WHERE is_alley = FALSE) as non_alley_count,
    COUNT(*) as total_count,
    ROUND(100.0 * COUNT(*) FILTER (WHERE is_alley = TRUE) / COUNT(*), 2) as alley_percentage
FROM chicago_ways;
