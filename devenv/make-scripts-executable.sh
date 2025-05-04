#!/bin/bash

# Make the shell scripts executable
cd $(dirname "$0")
chmod +x docker-start.sh
chmod +x docker-stop.sh
chmod +x docker-init-db.sh

echo "Shell scripts are now executable."
