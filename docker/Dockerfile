# k6 runner (pinned)
FROM grafana/k6:1.6.1

WORKDIR /tests
COPY loadtest/ /tests/

# Add a tiny Python uploader (boto3) for S3 upload
USER root
RUN apk add --no-cache python3 py3-boto3 ca-certificates && update-ca-certificates

COPY uploader/ /uploader/
COPY --chmod=0755 docker/entrypoint.sh /entrypoint.sh

# Back to non-root (grafana/k6 image uses user 12345)
USER 12345

ENTRYPOINT ["/entrypoint.sh"]
# Default only (ECS overrides command anyway)
CMD ["run", "/tests/scenarios/load.js"]