# Build the manager binary
FROM golang:1.24  as builder
RUN go env -w GOPROXY=direct

WORKDIR /workspace
# Copy the Go Modules manifests
COPY . .

# cache deps before building and copying source so that we don't need to re-download as much
# and so that source ch`anges don't invalidate our downloaded layer
RUN go mod download
RUN go mod tidy
# Copy the go source

# Build
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -a -o manager main.go

# Use distroless as minimal base image to package the manager binary
# Refer to https://github.com/GoogleContainerTools/distroless for more details
FROM gcr.io/distroless/static:nonroot
USER nonroot:nonroot
WORKDIR /
COPY --from=builder --chown=nonroot:nonroot  /workspace/manager .
COPY --from=builder --chown=nonroot:nonroot  /workspace/db/migrations ./db/migrations
ENV GIN_MODE=release
HEALTHCHECK CMD curl --fail http://localhost:8080 || exit 1
ENTRYPOINT ["/manager"]