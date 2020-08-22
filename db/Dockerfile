FROM mdillon/postgis:11

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc make cmake gdal-bin postgresql-server-dev-11 \
    expat libexpat1-dev libboost-dev libboost-graph-dev libboost-program-options-dev libpqxx-dev \
    wget ca-certificates

RUN wget -O pgrouting-3.1.0.tar.gz https://github.com/pgRouting/pgrouting/archive/v3.1.0.tar.gz && \
    tar xvfz pgrouting-3.1.0.tar.gz && \
    cd pgrouting-3.1.0 && \
    mkdir build && \
    cd build && \
    cmake .. && \
    make && \
    make install && \
    cd / && rm -Rf pgrouting-3.1.0*

RUN wget -O osm2pgrouting-2.3.6.tar.gz https://github.com/pgRouting/osm2pgrouting/archive/v2.3.6.tar.gz && \
    tar xvfz osm2pgrouting-2.3.6.tar.gz && \
    cd osm2pgrouting-2.3.6 && \
    cmake -H. -Bbuild && \
    cd build && \
    make && \
    make install && \
    cd / && rm -Rf osm2pgrouting-2.3.6*
