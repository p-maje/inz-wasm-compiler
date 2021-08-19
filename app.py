from flask import Flask, render_template, request, make_response
from parser import parse
import subprocess
import time
import os, re

app = Flask(__name__)


@app.route('/')
def hello_world():
    return render_template("base.html")


@app.route('/compile', methods=["POST"])
def compile_code():
    code = request.get_data(as_text=True)
    print(code)
    if code:
        # try:
        return parse(code), 200
        # except Exception as e:
        #     return str(e), 400
    return code, 400


@app.route('/run', methods=["POST"])
def run_code():
    code = request.get_data(as_text=True)
    tmp_file = f"tmp/{re.sub('[^a-zA-Z0-9]', '_', request.host)}_{time.time_ns()}.wat"
    if code:
        with open(tmp_file, 'x') as f:
            f.write(code)
        result = subprocess.run(["wat2wasm", tmp_file, "-o", "/dev/stdout"], stdout=subprocess.PIPE)
        binary = result.stdout
        os.remove(tmp_file)
        resp = make_response(binary, 200)
        resp.mimetype = 'application/wasm'
        return resp
    return code, 400


if __name__ == '__main__':
    app.run()
