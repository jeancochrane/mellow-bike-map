FROM python:3.8

RUN apt-get update && apt-get install -y --no-install-recommends gdal-bin

# Inside the container, create an app directory and switch into it
WORKDIR /app

# Install Python requirements
COPY ./requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

# Add a bogus env var for the Django secret key in order to allow us to run
# the 'collectstatic' management command
ENV DJANGO_SECRET_KEY 'foobar'

# Build static files into the container
RUN python manage.py collectstatic --noinput
