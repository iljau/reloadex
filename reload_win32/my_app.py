import atexit
from flask import Flask
app = Flask(__name__)


def app_atexit():
    print("app_atexit")


@app.route('/')
def hello_world():
    return 'Hello, World!'


def main():
    atexit.register(app_atexit)
    app.run()


def main_waitress():
    import waitress

    atexit.register(app_atexit)
    waitress.serve(app, host='127.0.0.1', port=8080)


if __name__ == "__main__":
    main()