FROM python:3
ENV PYTHONUNBUFFERED=1
COPY . /app
RUN --mount=type=cache,target=/root/.cache/pip pip install /app
CMD telegraf-mqtt-tests
