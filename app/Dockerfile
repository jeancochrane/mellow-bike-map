FROM python:3.8

# Add the NodeSource PPA
# (see: https://github.com/nodesource/distributions/blob/master/README.md)
RUN curl -sL https://deb.nodesource.com/setup_22.x | bash -

RUN apt-get update && apt-get install -y --no-install-recommends nodejs gdal-bin

WORKDIR /app/app

# Install Python requirements
COPY ./requirements.txt /app/app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Install Node requirements
COPY ./package.json ./package-lock.json ./
COPY ./patches ./patches
RUN npm install

# Copy all source code
COPY . .

# Bundle frontend code
RUN npm run build

# Add a bogus env var for the Django secret key in order to allow us to run
# the 'collectstatic' management command
# Build static files into the container
RUN DJANGO_SECRET_KEY='foobar' ENVIRONMENT='dev' python manage.py collectstatic --noinput
