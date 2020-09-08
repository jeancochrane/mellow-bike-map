FROM mdillon/postgis:11

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc make cmake gdal-bin postgresql-server-dev-11 \
    libboost-dev libboost-graph-dev \
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
