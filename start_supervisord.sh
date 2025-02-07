#!/bin/sh


# Set CONFIG_PATH to /config if it is not already set
export CONFIG_PATH=${CONFIG_PATH:-/config}

# Create the log directory
mkdir -p $CONFIG_PATH/log

# Start supervisord
/usr/bin/supervisord -c supervisord.conf
