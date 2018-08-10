reload_win32
-----------------------------

Restart wsgi server on Python code changes.

Installation:
```bash
pip install https://github.com/iljau/reload_win32/archive/master.zip#egg=reload_win32
```

Given example Flask application (saved as `my_app.py`), which is served by waitress.

```python
from flask import Flask
import waitress
app = Flask(__name__)

@app.route('/')
def hello_world():
    return 'Hello, World!'

def main():
    waitress.serve(app, host='127.0.0.1', port=8080)

if __name__ == "__main__":
    main()
```

To run this app with reloader .. :

```bash
reload my_app:main
```

.. or:
```bash
python -m reload_win32 my_app:main
```

Getting source for local development:
```bash
git clone git@github.com:iljau/reload_win32.git
cd reload_win32
pip install -e .
```