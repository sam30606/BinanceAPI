
FROM python:3.11

ENV APP_HOME /app
WORKDIR $APP_HOME
COPY . ./

RUN pip install -r requirements.txt
RUN pip install Flask gunicorn

ENV PORT 5000

CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 app:app