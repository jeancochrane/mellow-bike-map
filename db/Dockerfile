FROM postgis/postgis:16-3.4

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc make cmake gdal-bin postgresql-server-dev-16 \
    expat libexpat1-dev libboost-dev libboost-graph-dev libboost-program-options-dev libpqxx-dev \
    osmctools wget ca-certificates

RUN wget -O pgrouting-3.6.2.tar.gz https://github.com/pgRouting/pgrouting/archive/v3.6.2.tar.gz && \
    tar xvfz pgrouting-3.6.2.tar.gz && \
    cd pgrouting-3.6.2 && \
    mkdir build && \
    cd build && \
    cmake .. && \
    make && \
    make install && \
    cd / && rm -Rf pgrouting-3.6.2*

RUN wget -O osm2pgrouting-2.3.8.tar.gz https://github.com/pgRouting/osm2pgrouting/archive/v2.3.8.tar.gz && \
    tar xvfz osm2pgrouting-2.3.8.tar.gz && \
    cd osm2pgrouting-2.3.8 && \
    cmake -H. -Bbuild && \
    cd build && \
    make && \
    make install && \
    cd / && rm -Rf osm2pgrouting-2.3.8*
