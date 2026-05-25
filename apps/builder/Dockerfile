FROM moby/buildkit:rootless AS buildkit

FROM quay.io/centos/centos:stream9

COPY --from=buildkit /usr/bin/buildctl /usr/local/bin/buildctl
COPY --from=buildkit /usr/bin/buildctl-daemonless.sh /usr/local/bin/buildctl-daemonless.sh

RUN dnf install -y \
      buildah \
      fuse-overlayfs \
      git \
      python3 \
      python3-pip \
      shadow-utils \
      slirp4netns \
    && dnf clean all

RUN useradd --create-home --uid 10001 builder
WORKDIR /worker
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt
COPY worker ./worker

USER 10001
ENV BUILDKITD_FLAGS="--oci-worker-no-process-sandbox" \
    STORAGE_DRIVER="vfs"
CMD ["python3", "-m", "worker.main"]
