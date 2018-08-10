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