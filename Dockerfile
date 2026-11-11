FROM python:3.11-slim-bookworm

WORKDIR /app
COPY account.py bridge.py ./
USER 65534:65534
EXPOSE 18767
ENTRYPOINT ["python", "-u", "bridge.py", "--config", "/config/test-account.json"]
CMD ["--listen", "0.0.0.0"]
