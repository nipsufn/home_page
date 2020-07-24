import subprocess
from flask import Flask, render_template, request

app = Flask(__name__)

@app.route('/')
def index():
    app.logger.error("%s", str(request.args))
    if 'xmms2' in request.args:
        if 'xmms2request' in request.args and request.args['xmms2request'] == 'on':
            xmms2start = subprocess.Popen('/usr/bin/xmms2 play', shell=True)
        else:
            xmms2stop = subprocess.Popen('/usr/bin/xmms2 stop', shell=True)
    xmms2playing = subprocess.Popen('/usr/bin/xmms2 current | grep Playing', shell=True)
    streamdata = xmms2playing.communicate()[0]
    xmms2playing = xmms2playing.returncode
    app.logger.error("%s", str(xmms2playing))
    return render_template("index.html.j2", xmms2playing=xmms2playing)
