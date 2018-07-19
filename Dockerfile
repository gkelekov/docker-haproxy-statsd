#FROM python:2
FROM jfloff/alpine-python:2.7-slim

ADD templates/* /

RUN pip install requests

CMD [ "python", "-u", "./ha-stats.py" ]