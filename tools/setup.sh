#!/usr/bin/env bash

[ -d env ] && rm -rf env

python3 -m venv env
source env/bin/activate
python3 -m pip install --upgrade pip
pip install -r requirements.txt
