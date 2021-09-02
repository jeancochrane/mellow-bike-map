.PHONY: all
all: db/import/mellowroute.fixture db/import/chicago.table

db/import/%.fixture: app/mbm/fixtures/%.json
	(cd app && python manage.py loaddata $*) && touch $@

db/import/restrictions.table: db/import/chicago.table
	# Handle the fact that two-way streets only have one entry in OSM by
	# creating a union of chicago_ways with itself, reversing the source and
	# target for all two-way streets
	PGPASSWORD=postgres psql -U postgres -h postgres -d mbm -c " \
		CREATE TABLE restrictions AS \
			WITH chicago_ways_including_reversed AS ( \
				SELECT gid, name, source, target FROM chicago_ways \
				UNION \
				SELECT gid, name, target, source FROM chicago_ways where reverse_cost >= 0 \
			) \
			SELECT \
				CASE WHEN a.name = b.name THEN 0 ELSE 0.1 END AS to_cost, \
				b.target::integer AS target_id, \
				b.gid || ',' || a.gid AS via_path \
			FROM chicago_ways_including_reversed AS a \
			JOIN chicago_ways_including_reversed AS b \
			ON a.target = b.source \
			WHERE a.gid != b.gid" && \
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
