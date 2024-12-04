FROM python:3.11-alpine
LABEL "repository"="https://github.com/nasa-jpl/patch-version"
LABEL "homepage"="https://github.com/nasa-jpl/patch-version"
LABEL "maintainer"="Dennis Wai"

COPY requirements.txt requirements.txt

RUN apk --no-cache add git && pip install --no-cache-dir -r requirements.txt 

COPY entrypoint.py /entrypoint.py

ENTRYPOINT ["/entrypoint.py"]