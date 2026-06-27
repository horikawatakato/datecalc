"""
wsgi.py
-------
Gunicorn のエントリポイント。
DateCalc_server.py の Flask app オブジェクトをそのままエクスポートします。

  gunicorn --config gunicorn.conf.py wsgi:app
"""

from DateCalc_server import app  # noqa: F401  再エクスポート
