import os

bind                = "0.0.0.0:8000"
workers             = int(os.environ.get("WEB_CONCURRENCY", 2))  # CPU数から自動算出せず、WEB_CONCURRENCY で上書き可
worker_class        = "sync"
timeout             = 30    # nginx の proxy_read_timeout（既定60s）より短く保つ
accesslog           = "-"   # stdout
errorlog            = "-"   # stderr
loglevel            = "info"
max_requests        = 1000
max_requests_jitter = 50
