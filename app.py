import re
import traceback
import wasmer

from flask import Flask, render_template, request, make_response

from compiler import parse, CompilerException

app = Flask(__name__)


@app.route("/")
def hello_world():
    return render_template("base.html")


@app.route("/compile", methods=["POST"])
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


@app.route("/run", methods=["POST"])
def run_code():
    code = request.get_data(as_text=True)
    if code:
        binary = wasmer.wat2wasm(code)
        resp = make_response(binary, 200)
        resp.mimetype = "application/wasm"
        return resp
    return code, 400


if __name__ == "__main__":
    app.run()
