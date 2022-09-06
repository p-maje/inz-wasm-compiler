import re
import subprocess
import traceback
import time

from flask import Flask, render_template, request, make_response
from pathlib import Path

from compiler import parse, CompilerException

app = Flask(__name__)


@app.route('/')
def hello_world():
    return render_template("base.html")


@app.route('/compile', methods=["POST"])
def compile_code():
    code = request.get_data(as_text=True)
    print(code)
    if code:
        try:
            return parse(code), 200
        except CompilerException as e:
            print(traceback.format_exc())
            if re.match(r"\d+:", str(e)):
                return str(e), 400
            return "0:" + str(e), 400
    return code, 400


@app.route('/run', methods=["POST"])
def run_code():
    code = request.get_data(as_text=True)
    tmp_path = Path("tmp")
    tmp_path.mkdir(exist_ok=True)
    if code:
        tmp_file = tmp_path / f"{re.sub('[^a-zA-Z0-9]', '_', request.host)}_{time.time_ns()}.wat"
        tmp_file.write_text(code)
        result = subprocess.run(["wat2wasm", tmp_file, "-o", "/dev/stdout"], stdout=subprocess.PIPE)
        binary = result.stdout
        tmp_file.unlink()
        resp = make_response(binary, 200)
        resp.mimetype = 'application/wasm'
        return resp
    return code, 400


if __name__ == '__main__':
    app.run()
