#!/usr/bin/env python3

source env/bin/activate

# this is to warm up 1password and make sure that the auth is there before
# we proceed
op whoami

mv ~/Downloads/riverside*.mp3 .

op run --env-file="./.env" -- python3 podbean.py --scan