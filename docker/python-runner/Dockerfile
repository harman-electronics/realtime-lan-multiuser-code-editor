FROM python:3.14.0-slim-bookworm@sha256:d13fa0424035d290decef3d575cea23d1b7d5952cdf429df8f5542c71e961576

RUN groupadd --gid 10001 runner \
    && useradd --uid 10001 --gid 10001 --no-create-home \
        --home-dir /workspace --shell /usr/sbin/nologin runner \
    && python -m pip install --no-cache-dir \
        numpy==2.5.2 \
        pandas==3.0.5 \
        matplotlib==3.11.1 \
        sympy==1.14.0

COPY runner.sh /usr/local/bin/wifi-codeshare-python-runner
RUN chmod 0555 /usr/local/bin/wifi-codeshare-python-runner

USER 10001:10001
WORKDIR /workspace
ENTRYPOINT ["/usr/local/bin/wifi-codeshare-python-runner"]
