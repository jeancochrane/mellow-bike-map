.PHONY: all
all: db/import/mellowroute.fixture db/import/chicago.table

db/import/%.fixture: app/mbm/fixtures/%.json
	(cd app && python manage.py loaddata $*) && touch $@

db/import/chicago.table: db/raw/chicago-filtered.osm
	osm2pgrouting -f $< -c /usr/local/share/osm2pgrouting/mapconfig_for_bicycles.xml --prefix chicago_ --addnodes --tags --clean \
	              -d mbm -U postgres -h postgres -W postgres && \
	PGPASSWORD=postgres psql -U postgres -h postgres -d mbm -c " \
		UPDATE chicago_ways SET one_way = 2, oneway = 'NO', reverse_cost = cost \
		FROM osm_ways \
		WHERE osm_ways.osm_id = chicago_ways.osm_id \
		AND osm_ways.tags @> 'oneway:bicycle => no'" && \
	touch $@


db/raw/chicago-filtered.osm: db/raw/chicago-simplified.osm
	osmfilter $< \
		--keep="highway= bicycle= cycleway= route=bicycle" \
		--drop="building= amenity= shop= tourism= leisure= landuse= natural= power= waterway=" \
		--drop-author --drop-version \
		-o=$@


db/raw/chicago.osm:
	wget --no-use-server-timestamps -O $@ https://overpass-api.de/api/map?bbox=-87.8558,41.6229,-87.5085,42.0488
