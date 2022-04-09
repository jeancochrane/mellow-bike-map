.PHONY: all
all: db/import/mellowroute.fixture db/import/chicago.table

db/import/%.fixture: app/mbm/fixtures/%.json
	(cd app && python manage.py loaddata $*) && touch $@

db/import/shooting_star_ways.table: db/import/chicago.table
	# Alter chicago_ways to
	PGPASSWORD=postgres psql -U postgres -h postgres -d mbm -c " \
		CREATE TABLE shooting_star_ways AS \
			WITH shooting_star_matrix AS ( \
				SELECT \
					b.name, b.gid, b.source, b.target, b.cost, b.x1, b.y1, b.x2, b.y2, \
					a.gid AS rule, \
					CASE WHEN b.name = a.name THEN 0 ELSE 0.1 END AS to_cost \
				FROM temp_ways AS a \
				JOIN temp_ways AS b \
				ON a.target = b.source \
			    WHERE a.gid != b.gid \
			    UNION \
			    SELECT \
			    	a.name, a.gid, a.source, a.target, a.cost, a.x1, a.y1, a.x2, a.y2, \
			    	null as rule, \
			    	0 as to_cost \
			    FROM temp_ways AS a \
			    LEFT JOIN temp_ways AS b \
			    ON a.source = b.target \
			    WHERE b.gid IS null \
 			) \
 			SELECT name, gid, source, target, cost, x1, y1, x2, y2, to_cost, \
 			STRING_AGG(rule::text, ',') AS rule \
 			FROM shooting_star_matrix \
 			GROUP BY name, gid, source, target, cost, x1, y1, x2, y2, to_cost" && \
	touch $@

db/import/chicago.table: db/raw/chicago-filtered.osm
	osm2pgrouting -f $< -c /usr/local/share/osm2pgrouting/mapconfig_for_bicycles.xml --prefix chicago_ --addnodes --tags --clean \
	              -d mbm -U postgres -h postgres -W postgres && \
	PGPASSWORD=postgres psql -U postgres -h postgres -d mbm -c " \
		UPDATE chicago_ways SET one_way = 2, oneway = 'NO', reverse_cost = cost \
		FROM osm_ways \
		WHERE osm_ways.osm_id = chicago_ways.osm_id \
		AND osm_ways.tags @> 'oneway:bicycle => no'" && \
	touch $@


db/raw/chicago-filtered.osm: db/raw/chicago.osm
	osmconvert $< --drop-author --drop-version --out-osm -o="$@"


db/raw/chicago.osm:
	wget --no-use-server-timestamps -O $@ https://overpass-api.de/api/map?bbox=-87.8558,41.6229,-87.5085,42.0488
