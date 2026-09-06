FROM docker.io/library/golang@sha256:fb612b7831d53a89cbc0aaa7855b69ad7b0caf603715860cf538df854d047b84 AS build
ENV GOTOOLCHAIN=local CGO_ENABLED=0 GOOS=linux GOARCH=amd64
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN REPO_ROOT=/src go test -mod=readonly ./pkg/cloud -args '-ginkgo.label-filter=!integ'
RUN go build -mod=readonly -trimpath -buildvcs=false -ldflags '-s -w -extldflags -static' -o /out/manager .
RUN cd hack/tools && go build -mod=readonly -trimpath -buildvcs=false -o /out/kustomize sigs.k8s.io/kustomize/kustomize/v5
FROM scratch AS tools
COPY --from=build /out/kustomize /kustomize
FROM gcr.io/distroless/static@sha256:1c2c046bc09ed40fad370b599a0b1ae7987f55b01e247cf27a7c27cd97e5bbc7 AS runtime
COPY --from=build /out/manager /manager
USER 65532:65532
ENTRYPOINT ["/manager"]
