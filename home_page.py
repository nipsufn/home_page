import subprocess
from flask import Flask, render_template, request

APP = Flask(__name__)

@APP.route('/', methods=['GET', 'POST'])
def index():
    APP.logger.error("%s", str(request.form))
    if 'xmms2url' in request.form:
        if 'xmms2request' in request.form and request.form['xmms2request'] == 'on':
            subprocess.Popen('/usr/bin/xmms2 server volume 100', shell=True)
            subprocess.Popen('/usr/bin/xmms2 add ' + request.form['xmms2url'], shell=True)
            subprocess.Popen('/usr/bin/xmms2 play', shell=True)
        else:
            subprocess.Popen('/usr/bin/xmms2 stop', shell=True)
            subprocess.Popen('/usr/bin/xmms2 remove 1', shell=True)
    
    xmms2playing = subprocess.Popen('/usr/bin/xmms2 current | grep Playing', shell=True)
    xmms2playing.communicate()[0]
    xmms2playing = xmms2playing.returncode

    xmms2volume = subprocess.Popen('xmms2 server volume | head -n1 | cut -d' ' -f3', shell=True)
    xmms2volume = xmms2volume.communicate()[0]

    APP.logger.error("%s", str(xmms2playing))
    return render_template("index.html.j2", xmms2playing=xmms2playing, xmms2volume=xmms2volume)
