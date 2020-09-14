#!/bin/bash
set -euo pipefail

# Make sure the deployment group specific variables are available to this
# script.
source /home/mbm/mellow-bike-map/configs/$DEPLOYMENT_GROUP_NAME-config.conf

# Set some useful variables
DEPLOYMENT_NAME="$APP_NAME-$DEPLOYMENT_ID"
PROJECT_DIR="/home/mbm/$DEPLOYMENT_NAME"
VENV_DIR="/home/mbm/.virtualenvs/$DEPLOYMENT_NAME"

# Move the contents of the folder that CodeDeploy used to "Install" the app to
# the deployment specific folder
mv /home/mbm/mellow-bike-map $PROJECT_DIR

# Create a deployment specific virtual environment
python3 -m venv $VENV_DIR

# Set the ownership of the project files and the virtual environment
chown -R mbm.www-data $PROJECT_DIR
chown -R mbm.www-data $VENV_DIR

# Upgrade pip and setuptools. This is needed because sometimes python packages
# that we rely upon will use more recent packaging methods than the ones
# understood by the versions of pip and setuptools that ship with the operating
# system packages.
sudo -H -u mbm $VENV_DIR/bin/pip install --upgrade pip
sudo -H -u mbm $VENV_DIR/bin/pip install --upgrade "setuptools<50.0"

# Install the project requirements into the deployment specific virtual
# environment.
sudo -H -u mbm $VENV_DIR/bin/pip install -r $PROJECT_DIR/app/requirements.txt --upgrade

# OPTIONAL If you're using PostgreSQL, check to see if the database that you
# need is present and, if not, create it setting the mbm user as it's
# owner.
psql -U postgres -tc "SELECT 1 FROM pg_database WHERE datname = 'mbm'" | grep -q 1 || createdb -U postgres -O mbm mbm

# OPTIONAL Create any extensions within your database that your project needs.
psql -U postgres -d mbm -f $PROJECT_DIR/db/create-extensions.sql

# OPTIONAL Run migrations and other management commands that should be run with
# every deployment
export DJANGO_SECRET_KEY=temporarykey
sudo -H -u mbm $VENV_DIR/bin/python $PROJECT_DIR/app/manage.py migrate
sudo -H -u mbm $VENV_DIR/bin/python $PROJECT_DIR/app/manage.py createcachetable
sudo -H -u mbm $VENV_DIR/bin/python $PROJECT_DIR/app/manage.py collectstatic --no-input
unset DJANGO_SECRET_KEY

# Echo a simple nginx configuration into the correct place, and tell
# certbot to request a cert if one does not already exist.
# Wondering about the DOMAIN variable? It becomes available by source-ing
# the config file (see above).
if [ ! -f /etc/letsencrypt/live/$DOMAIN/fullchain.pem ]; then
    echo "server {
        listen 80;
        server_name $DOMAIN;
        location ~ .well-known/acme-challenge {
            root /usr/share/nginx/html;
            default_type text/plain;
        }
    }" > /etc/nginx/conf.d/$APP_NAME.conf
    service nginx reload
    certbot -n --nginx -d $DOMAIN -m jean@jeancochrane.com --agree-tos
fi

# Install Jinja into the virtual environment and run the render_configs.py
# script.
$VENV_DIR/bin/pip install Jinja2==2.10
$VENV_DIR/bin/python $PROJECT_DIR/scripts/render_configs.py $DEPLOYMENT_ID $DEPLOYMENT_GROUP_NAME $DOMAIN $APP_NAME

# Write out the deployment ID to a Python module that can get imported by the
# app and returned by the /pong/ route (see above).
echo "DEPLOYMENT_ID='$DEPLOYMENT_ID'" > $PROJECT_DIR/app/mbm/deployment.py
