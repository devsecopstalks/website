```
bash setup.sh
source env/bin/activate
export PODBEAN_CLIENT_ID=id
export PODBEAN_CLIENT_SECRET=secret
python3 podbean.py ~/Downloads/podcast63-ai\ tools.mp3
```

or

```
bash setup.sh
source env/bin/activate
# copy file into the directory and use 1password to fill
# env variables and scan directory for mp3 files
op run --env-file="./.env" -- python3 podbean.py --scan
```