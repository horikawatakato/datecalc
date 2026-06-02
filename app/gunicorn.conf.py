import os

bind        = "0.0.0.0:8000"
workers     = int(os.environ.get("WEB_CONCURRENCY", 2))  # コンテナ資源に合わせ固定
worker_class = "sync"
timeout     = 120
accesslog   = "-"   # stdout
errorlog    = "-"   # stderr
loglevel    = "info"
max_requests        = 1000
max_requests_jitter = 50
