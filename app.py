from flask import Flask, render_template, request
from parser import parse

app = Flask(__name__)


@app.route('/')
def hello_world():
    return render_template("base.html")


@app.route('/compile', methods=["POST"])
def compile_code():
    code = request.get_data(as_text=True)
    print(code)
    return parse(code), 200


if __name__ == '__main__':
    app.run()
