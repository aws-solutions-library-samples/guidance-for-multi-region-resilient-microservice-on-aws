FROM node:20-alpine3.21
#
#RUN yum install -q -y libstdc++.i686 glibc.i686 tar gzip xz shadow-utils && \
#    yum clean all

ENV APPUSER=appuser
ENV APPUID=1001
ENV APPGID=1000

#ENV USER=docker
#ENV UID=12345
#ENV GID=23456

#RUN adduser \
#    --disabled-password \
#    --gecos "" \
#    --home "$(pwd)" \
#    --ingroup "$USER" \
#    --no-create-home \
#    --uid "$UID" \
#    "$USER" \

RUN adduser \
    --home "/app" \
#    --ingroup "$APPUSER" \
    --uid "$APPUID" \
    --disabled-password \
    "$APPUSER"
#
#ARG TARGETARCH
#ENV NODE_VERSION 16.18.1

#RUN DEBARCH="$TARGETARCH"; \
#    if [ "$DEBARCH" = "amd64" ]; then DEBARCH=x64; fi; \
#    echo "Pulling https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-${DEBARCH}.tar.xz" && \
#    curl -LSs https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-${DEBARCH}.tar.xz -o node.tar.xz && \
#    tar xf node.tar.xz --directory /tmp && \
#    cp -R /tmp/node-v${NODE_VERSION}-linux-${DEBARCH}/* /usr && \
#    rm -rf node-v${NODE_VERSION}-linux-${DEBARCH} node.tar.xz

WORKDIR /app
USER appuser

COPY --chown=appuser:appuser package.json .
COPY --chown=appuser:appuser package-lock.json .

RUN npm ci
HEALTHCHECK CMD curl --fail http://localhost:8080 || exit 1
COPY . /app
RUN npm run build

ENTRYPOINT [ "node", "dist/main.js" ]