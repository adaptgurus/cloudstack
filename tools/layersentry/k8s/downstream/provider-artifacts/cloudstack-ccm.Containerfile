FROM docker.io/library/golang@sha256:fb612b7831d53a89cbc0aaa7855b69ad7b0caf603715860cf538df854d047b84 AS build
ENV GOTOOLCHAIN=local CGO_ENABLED=0 GOOS=linux GOARCH=amd64
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN go test -mod=readonly ./...
ARG SOURCE_COMMIT
ARG SOURCE_DATE
RUN go build -mod=readonly -trimpath -buildvcs=false -ldflags "-s -w -X k8s.io/component-base/version.gitVersion=v1.2.0-layersentry.k8s1.36 -X k8s.io/component-base/version.gitCommit=${SOURCE_COMMIT} -X k8s.io/component-base/version.buildDate=${SOURCE_DATE}" -o /out/cloudstack-ccm ./cmd/cloudstack-ccm
FROM gcr.io/distroless/static@sha256:1c2c046bc09ed40fad370b599a0b1ae7987f55b01e247cf27a7c27cd97e5bbc7 AS runtime
COPY --from=build /out/cloudstack-ccm /app/cloudstack-ccm
USER 65532:65532
ENTRYPOINT ["/app/cloudstack-ccm", "--cloud-provider", "external-cloudstack"]
