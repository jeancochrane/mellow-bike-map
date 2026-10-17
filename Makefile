.PHONY: all
all: db/import/mellowroute.fixture db/import/chicago.table

db/import/%.fixture: app/mbm/fixtures/%.json
	(cd app && python manage.py loaddata $*) && touch $@

db/import/chicago.table: db/raw/chicago-filtered.osm
	osm2pgrouting -f $< -c /usr/local/share/osm2pgrouting/mapconfig_for_bicycles.xml --prefix chicago_ --addnodes --tags --clean \
	              -d mbm -U postgres -h postgres -W postgres && \
	PGPASSWORD=postgres psql -U postgres -h postgres -d mbm -c " \
		CREATE INDEX ON chicago_ways(osm_id); \
		UPDATE chicago_ways SET one_way = 2, oneway = 'NO', reverse_cost = cost \
		FROM osm_ways \
		WHERE osm_ways.osm_id = chicago_ways.osm_id \
		AND osm_ways.tags @> 'oneway:bicycle => no';" && \
	touch $@


db/raw/chicago-filtered.osm: db/raw/chicago.osm
	osmfilter $< \
		--keep="highway= bicycle= cycleway= route=bicycle" \
		--drop="building= amenity= shop= tourism= leisure= landuse= natural= power= waterway=" \
		--drop-author --drop-version \
		-o=$@


db/raw/chicago.osm: db/chicago.overpassql
	curl -f -A mellow-bike-map -o $@ \
		--data-urlencode data@$< \
		https://overpass-api.de/api/interpreter