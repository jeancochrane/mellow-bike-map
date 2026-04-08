from django.db import migrations, models

from mbm.constants import SIDEWALK_TAG_IDS

# Create a materialized view that drops sidewalks, keeping only sidewalks
# that are tagged as mellow routes.
#
# This particular query structure is designed to execute as quickly as
# possible, since we refresh this view every time we add, edit, or delete
# MellowRoutes.
SIDEWALK_TAG_IDS_STR = ", ".join(str(id) for id in SIDEWALK_TAG_IDS)
CREATE_VIEW = f"""
CREATE MATERIALIZED VIEW IF NOT EXISTS clean_ways AS
SELECT *
FROM chicago_ways
WHERE tag_id NOT IN ({SIDEWALK_TAG_IDS_STR})
UNION ALL
SELECT cw.*
FROM chicago_ways cw
INNER JOIN (
    SELECT DISTINCT UNNEST(ways) AS osm_id
    FROM mbm_mellowroute
) AS mellow_sidewalks
    ON cw.osm_id = mellow_sidewalks.osm_id
WHERE cw.tag_id IN ({SIDEWALK_TAG_IDS_STR});

CREATE UNIQUE INDEX IF NOT EXISTS clean_ways_gid_idx ON clean_ways (gid);
CREATE INDEX IF NOT EXISTS clean_ways_osm_id_idx ON clean_ways (osm_id);
CREATE INDEX IF NOT EXISTS clean_ways_source_idx ON clean_ways (source);
CREATE INDEX IF NOT EXISTS clean_ways_target_idx ON clean_ways (target);
CREATE INDEX IF NOT EXISTS clean_ways_the_geom_idx ON clean_ways USING gist (the_geom);
"""

DROP_VIEW = "DROP MATERIALIZED VIEW IF EXISTS clean_ways;"

# Also add a database trigger that refreshes the materialized view whenever
# we add, edit, or delete from our mellow routes list
CREATE_FUNCTION = """
CREATE OR REPLACE FUNCTION refresh_clean_ways() RETURNS trigger AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY clean_ways;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;
"""

DROP_FUNCTION = "DROP FUNCTION IF EXISTS refresh_clean_ways();"

CREATE_TRIGGER = """
CREATE TRIGGER refresh_clean_ways_on_mellowroute_edit
    AFTER INSERT OR UPDATE OR DELETE ON mbm_mellowroute
    FOR EACH STATEMENT
    EXECUTE FUNCTION refresh_clean_ways();
"""

DROP_TRIGGER = """
DROP TRIGGER IF EXISTS refresh_clean_ways_on_mellowroute_edit ON mbm_mellowroute;
"""


class Migration(migrations.Migration):

    dependencies = [
        ('mbm', '0003_populate_mellowroute_type_sidewalk'),
    ]

    operations = [
        migrations.RunSQL(CREATE_VIEW, reverse_sql=DROP_VIEW),
        migrations.RunSQL(CREATE_FUNCTION, reverse_sql=DROP_FUNCTION),
        migrations.RunSQL(CREATE_TRIGGER, reverse_sql=DROP_TRIGGER),
    ]
