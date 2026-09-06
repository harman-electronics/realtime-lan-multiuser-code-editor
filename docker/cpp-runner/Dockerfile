FROM gcc:14.2.0-bookworm@sha256:b99b86a28812b1e6453a231a947dc43d76fe192788a12f344a9b568bf9f5d24c

RUN groupadd --gid 10001 runner \
    && useradd --uid 10001 --gid 10001 --no-create-home \
        --home-dir /workspace --shell /usr/sbin/nologin runner

COPY runner.sh /usr/local/bin/wifi-codeshare-cpp-runner
RUN chmod 0555 /usr/local/bin/wifi-codeshare-cpp-runner

USER 10001:10001
WORKDIR /workspace
ENTRYPOINT ["/usr/local/bin/wifi-codeshare-cpp-runner"]
