FROM python:3.12

# Add the NodeSource PPA
# (see: https://github.com/nodesource/distributions/blob/master/README.md)
RUN curl -sL https://deb.nodesource.com/setup_22.x | bash -

RUN apt-get update && apt-get install -y --no-install-recommends nodejs gdal-bin

# Inside the container, create an app directory and switch into it
RUN mkdir -p /app/app
WORKDIR /app/app

# Install Python requirements
RUN pip install --upgrade pip
COPY ./requirements.txt /app/app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Install Node requirements
COPY ./package.json /app/app/package.json
RUN npm install

COPY . /app/app

# Add a bogus env var for the Django secret key in order to allow us to run
# the 'collectstatic' management command
ENV DJANGO_SECRET_KEY 'foobar'

# Build static files into the container
RUN python manage.py collectstatic --noinput
