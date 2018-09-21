reloadex
-----------------------------

Restart wsgi server on Python code changes.

---

### Installation and usage

Install:
```bash
pip install reloadex
```

Install from git:
```bash
pip install https://github.com/iljau/reloadex/archive/master.zip#egg=reloadex
```

Given example [Flask](https://github.com/pallets/flask) application.

```python
from flask import Flask
app = Flask(__name__)

@app.route('/')
def hello_world():
    return 'Hello, World!'

def main():
    app.run()

if __name__ == "__main__":
    main()
```

To run this app with reloader specify module name or filename, with main function:

```bash
reload my_app:main
reload my_app.py:main
```

By default `main` function is invoked, so above simplifies to:
```bash
reload my_app
reload my_app.py
```

Using python module invocation also works:
```bash
python -m reloadex my_app:main
```

Reloader uses current working directory as root: there it looks for `.reloadignore` and recursively watches all subdirectories.

---

### Getting source for local development
```bash
git clone git@github.com:iljau/reloadex.git
cd reloadex
pip install -e .
```