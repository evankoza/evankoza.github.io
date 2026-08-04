# The nightly wildfire refresh, packaged to run on the home server.
#
# It moved off GitHub Actions because CIFFC's API answers 403 to Azure IP
# ranges: the identical request, same User-Agent, succeeds from a Canadian
# residential connection and fails from a hosted runner. That is their access
# decision, so the job goes to a machine they already allow rather than around
# the block.
#
# Dependencies are installed from the model repo's own pyproject at build time,
# so this file never restates the dependency list. The package is re-pulled and
# reinstalled at each run (see entrypoint.sh), which means an upstream model
# change reaches the server on the next night without a rebuild. Rebuild only
# when the DEPENDENCIES change.
FROM python:3.12-slim

# libgomp1 is LightGBM's OpenMP runtime; git is how both repos arrive and how
# the finished page leaves; tzdata so the schedule honours America/Toronto.
RUN apt-get update && apt-get install -y --no-install-recommends \
        git ca-certificates libgomp1 tzdata \
    && rm -rf /var/lib/apt/lists/*

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1 \
    WILDFIRE_DATA_DIR=/data/wildfire

ARG MODEL_REPO=https://github.com/evankoza/wildfire-forecast.git
RUN git clone --depth 50 "$MODEL_REPO" /opt/wildfire \
    && pip install -e /opt/wildfire

WORKDIR /app
COPY refresh.sh entrypoint.sh /app/
RUN chmod +x /app/refresh.sh /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
