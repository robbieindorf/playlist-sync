FROM python:alpine

WORKDIR /app/
COPY spotify-sync.py /app/spotify-sync.py
COPY requirements.txt /app/requirements.txt

RUN pip install -r requirements.txt

CMD python spotify-sync.py
