#!/bin/sh

set -eu

rm -f ./lambda.zip

python3 -m venv ./venv

(
    . ./venv/bin/activate
    pip3 install -r ./requirements.txt > /dev/null
)

mkdir -p ./archive
rsync -aK --exclude '__pycache__' --exclude '.pyc' ./venv/lib/python3.6/site-packages/ ./archive/
rsync -aK --exclude '__pycache__' --exclude '.pyc' ./src/ ./archive/

(
    cd ./archive
    zip -r ./lambda.zip . > /dev/null
)

mv ./archive/lambda.zip ./
rm -rf ./archive
