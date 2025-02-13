.PHONY: all
all: db/import/mellowroute.fixture db/import/chicago.table db/import/montreal.table

db/import/%.fixture: app/mbm/fixtures/%.json
	(cd app && python manage.py loaddata $*) && touch $@

#### CHICAGO ####

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
	wget --no-use-server-timestamps -O $@ https://overpass-api.de/api/map?bbox=

#### MONTREAL ####

db/import/montreal.table: db/raw/montreal-filtered.osm
	osm2pgrouting -f $< -c /usr/local/share/osm2pgrouting/mapconfig_for_bicycles.xml --prefix montreal_ --addnodes --tags --clean \
	              -d mbm -U postgres -h postgres -W postgres && \
	PGPASSWORD=postgres psql -U postgres -h postgres -d mbm -c " \
		UPDATE montreal_ways SET one_way = 2, oneway = 'NO', reverse_cost = cost \
		FROM osm_ways \
		WHERE osm_ways.osm_id = montreal_ways.osm_id \
		AND osm_ways.tags @> 'oneway:bicycle => no'" && \
	touch $@
	
db/raw/montreal-filtered.osm: db/raw/montreal.osm
	osmconvert $< --drop-author --drop-version --out-osm -o="$@"
	
db/raw/montreal.osm:
	wget --no-use-server-timestamps -O $@ https://overpass-api.de/api/map?bbox=-74.0227,45.3754,-73.3937,45.7552
