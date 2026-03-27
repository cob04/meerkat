FROM alpine:3.21

RUN apk add --no-cache curl libstdc++ libgcc

RUN curl -sLO https://github.com/tailwindlabs/tailwindcss/releases/download/v4.1.3/tailwindcss-linux-x64-musl \
    && chmod +x tailwindcss-linux-x64-musl \
    && mv tailwindcss-linux-x64-musl /usr/local/bin/tailwindcss

WORKDIR /app

ENTRYPOINT ["tailwindcss"]
