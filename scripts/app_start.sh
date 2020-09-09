#!/bin/bash
set -euo pipefail

# Make sure the deployment group specific variables are available to this
# script.
source ${BASH_SOURCE%/*}/../configs/$DEPLOYMENT_GROUP_NAME-config.conf

# Set some useful variables
PROJECT_DIR="/home/mbm/$APP_NAME-$DEPLOYMENT_ID"

# Re-read supervisor config, and add new processes
supervisorctl reread
supervisorctl add $APP_NAME-$DEPLOYMENT_ID

# Check to see if our /pong/ endpoint responds with the correct deployment ID.

loop_counter=0
while true; do
    # check to see if the socket file that the gunicorn process that is running
    # the app has been created. If not, wait for a second.
    if [[ -e /tmp/$APP_NAME-${DEPLOYMENT_ID}.sock ]]; then

        # Pipe an HTTP request into the netcat tool (nc) and grep the response
        # for the deployment ID. If it's not there, wait for a second.
        running_app=`printf "GET /pong/ HTTP/1.1 \r\nHost: localhost \r\n\r\n" | nc -U /tmp/$APP_NAME-${DEPLOYMENT_ID}.sock | grep -e "$DEPLOYMENT_ID" -e 'Bad deployment*'`
        echo $running_app
        if [[ $running_app == $DEPLOYMENT_ID ]] ; then
            echo "App matching $DEPLOYMENT_ID started"
            break
        elif [[ $loop_counter -ge 20 ]]; then
            echo "Application matching deployment $DEPLOYMENT_ID has failed to start"
            exit 99
        else
            echo "Waiting for app $DEPLOYMENT_ID to start"
            sleep 1
        fi
    elif [[ $loop_counter -ge 20 ]]; then
        echo "Application matching deployment $DEPLOYMENT_ID has failed to start"
        exit 99
    else
        echo "Waiting for socket $APP_NAME-$DEPLOYMENT_ID.sock to be created"
        sleep 1
    fi
    loop_counter=$(expr $loop_counter + 1)
done

# If everything is OK, check the integrity of the nginx configuration and
# reload (or start for the first time) Nginx. Because of the pipefail setting
# at the beginning of this script, if any of the configuration files that Nginx
# knows about contain errors, this will cause this script to exit with a non-zero
# status and cause the deployment as a whole to fail.

echo "Reloading nginx"
nginx -t
service nginx reload || service nginx start

# It's safe to terminate the older version of the site
# by sending the TERM signal to old gunicorn processes.
# This code block iterates over deployments for a particular deployment group,
# checks each status (is it "RUNNING"?), and terminates the old, running deployment.
old_deployments=`(ls /opt/codedeploy-agent/deployment-root/$DEPLOYMENT_GROUP_ID | grep -Po "d-[A-Z0-9]{9}") || echo ''`
for deployment in $old_deployments; do
    if [[ ! $deployment == $DEPLOYMENT_ID ]]; then
        echo "Signalling application processes from $deployment"

        STATUS=`supervisorctl status $APP_NAME-$deployment:*`
        if [[ $STATUS == *"RUNNING"* ]]; then
            supervisorctl signal TERM $APP_NAME-$deployment:*
        fi
    fi
done;

# Cleanup all versions except the most recent 3. This uses the find command to
# search for directories within the home directory of the mbm user, sorts
# them by when they were created, then filters them down to only the directory
# names that are for our project and reduces them down to the top three in the
# list (which should be the most recent)

old_versions=`(find /home/mbm -maxdepth 1 -type d -printf '%TY-%Tm-%Td %TT %p\n' | sort -r | grep -Po "/home/mbm/$APP_NAME-d-[A-Z0-9]{9}" | tail -n +4) || echo ''`
for version in $old_versions; do
    echo "Removing $version"
    rm -rf $version
done;

# Cleanup virtualenvs except the most recent 3. This uses the same approach as
# above but for virtual environments rather than the code directories.
old_venvs=`(find /home/mbm/.virtualenvs -maxdepth 1 -type d -printf '%TY-%Tm-%Td %TT %p\n' | sort -r | grep -Po "/home/mbm/\.virtualenvs/$APP_NAME-d-[A-Z0-9]{9}" | tail -n +4) || echo ''`
for venv in $old_venvs; do
    echo "Removing $venv"
    rm -rf $venv
done;

# Remove old processes from supervisor. Search the output of the status command
# of Supervisor for those processes that have exited, are stopped or died on
# their own and look for the ones that are for our project. The processes that we
# sent the TERM signal to above should be amongst these.

old_procs=`(supervisorctl status | grep -P '(EXITED|STOPPED|FATAL)' | grep -Po "$APP_NAME-d-[A-Z0-9]{9}") || echo ''`
for proc in $old_procs; do
    echo "Removing $proc"
    supervisorctl remove $proc
done;
