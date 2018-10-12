reloadex
-----------------------------

Restart wsgi server on Python code changes. Works on Windows and Linux.

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

To run this app with reloader specify module name, filename or command. Following invocations are supported:

```bash
reloadex my_app.py
reloadex my_app.py:main
reloadex my_app:main
reloadex --cmd "python my_app.py"
reloadex --cmd python my_app.py
```

Using python module invocation also works:
```bash
python -m reloadex my_app.py
```

Reloader uses current working directory as root: there it looks for `.reloadignore` and recursively watches all subdirectories.
If `.reloadignore` is not found, reloads happen on `*.py` file changes.

---

### Getting source for local development
```bash
git clone git@github.com:iljau/reloadex.git
cd reloadex
pip install -e .
```
