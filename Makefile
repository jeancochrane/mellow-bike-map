db/raw/chicago.osm:
	wget --no-use-server-timestamps -O $@ https://overpass-api.de/api/map?bbox=-87.7488,41.7170,-87.5157,42.0003

db/import/chicago.table: db/raw/chicago.osm
	osm2pgrouting -f $< -c /usr/local/share/osm2pgrouting/mapconfig_for_bicycles.xml --prefix chicago_ --addnodes --tags --clean \
	              -d mellow_bike_map -U postgres -h postgres -W postgres && \
	touch $@
