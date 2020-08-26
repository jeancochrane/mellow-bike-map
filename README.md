# mellow-bike-map

Experimenting with an improved routing algorithm for biking in Chicago.

## Developing

Development requires Docker and Docker Compose.

Build containers:

```
docker-compose build
```

Import the data:

```
docker-compose -f docker-compose.yml -f db/docker-compose.yml run --rm make db/import/chicago.table
```

Start the app service:

```
docker-compose up
```

The app will be available on http://localhost:8000.

## Mapping

Load the region fixtures:

```
docker-compose run --rm app ./manage.py loaddata mellowway
```

Navigate to http://localhost:8000/ways and use the "Edit" buttons to start mapping.
