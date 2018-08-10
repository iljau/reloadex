reload_win32
-----------------------------

Restart wsgi server on Python code changes.

Installation:
```bash
pip install https://github.com/iljau/reload_win32/archive/master.zip#egg=reload_win32
```

Given example Flask application saved as `myapp.py`

```python
from flask import Flask
app = Flask(__name__)

@app.route('/')
def hello_world():
    return 'Hello, World!'
```

To run this app with reloader:

```bash
reload my_app:app.wsgi_app
```

Getting source for local development:
```bash
git clone git@github.com:iljau/reload_win32.git
cd reload_win32
pip install -e .
```