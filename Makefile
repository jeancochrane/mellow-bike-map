.PHONY: all
all: db/import/mellowroute.table db/import/chicago.table

db/import/mellowroute.table: app/mbm/fixtures/mellowroute.json
	python manage.py loaddata $< && touch $@

db/import/chicago.table: db/raw/chicago.osm
	osm2pgrouting -f $< -c /usr/local/share/osm2pgrouting/mapconfig_for_bicycles.xml --prefix chicago_ --addnodes --tags --clean \
	              -d mbm -U postgres -h postgres -W postgres && \
	PGPASSWORD=postgres psql -U postgres -h postgres -d mbm -c " \
		UPDATE chicago_ways SET one_way = 2, oneway = 'NO', reverse_cost = cost \
		FROM osm_ways \
		WHERE osm_ways.osm_id = chicago_ways.osm_id \
		AND osm_ways.tags @> 'oneway:bicycle => no'" && \
	touch $@

db/raw/chicago.osm:
	wget --no-use-server-timestamps -O $@ https://overpass-api.de/api/map?bbox=-87.7488,41.7170,-87.5157,42.0003
