let input, output, error
function init() {
    CodeMirror.defineSimpleMode("simplemode", {
        start: [
            {regex: /(def|int|float)(\s+)(\w+)\(/, token: ["keyword", null, "variable-2"]},
            {
                regex: /(?:return|if|for|while|else|write|with|from|to|downto)\b/,
                token: "keyword"
            },
            {regex: /"[^"]*"/, token: "string"},
            {regex: /-?(?:\d+\.?\d*)/, token: "number"},
            {regex: /[-+\/*=<>!%]+/, token: "operator"},
            {regex: /\{/, indent: true},
            {regex: /\}/, dedent: true},
            {regex: /[a-z$][\w$]*/, token: "variable"}
        ]
    });
    input = CodeMirror.fromTextArea(document.getElementById('input'), {
        theme: 'darcula',
        lineNumbers: true,
        lineWrapping: true,
        autoCloseBrackets: true
    });
    input.setSize("", "90%")
    output = CodeMirror.fromTextArea(document.getElementById('output'), {
        theme: 'darcula',
        lineNumbers: true,
        lineWrapping: true,
        readOnly: true
    });
    output.setSize("", "50%")
    error = null
    input.setValue("def main() {\n\ \ write 11\n}")
}

function compile() {
    let code = input.getValue()
    if (error !== null) {
        input.removeLineClass(error.line, "text", "error-line")
        input.removeLineWidget(error.widget)
    }

    fetch('/compile', {
        method: 'POST',
        body: code,
    }).then(
        (response) => ({status: response.status, text: response.text()})
    ).then(
        (obj) => {
            obj.text.then(
                (text) => {
                    if (obj.status === 400) {
                        console.log(text)

                        let tokens = text.split(":")
                        let element = document.createElement("div")
                        element.appendChild(document.createTextNode("🡱 " + tokens[1]))
                        element.className = "compilation-error"
                        error = {
                            line: input.addLineClass(tokens[0] - 1, "text", "error-line"),
                            widget: input.addLineWidget(tokens[0] - 1, element)
                        }
                    }
                    output.setValue(text)
                }
            )
        }
    )
}

function run() {
    let code = output.getValue()
    let console_area = document.getElementById("console")
    let importObject = {
        imports: {write: (arg) => console_area.value += '> ' + arg + '\n'}
    }

    console_area.value = ''
    WebAssembly.instantiateStreaming(fetch('/run', {
        method: 'POST',
        body: code,
        response_type: 'application/wasm'
    }), importObject).then(obj => {
        obj.instance.exports.main()
        console_area.value += 'DONE\n'
    })
}