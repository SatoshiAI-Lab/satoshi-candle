FROM python:3.12.2-alpine3.18 AS build

RUN pip install --upgrade pip
RUN pip install fastapi uvicorn[standard] httpx[http2] websockets

FROM build AS deploy

WORKDIR /app

COPY . .