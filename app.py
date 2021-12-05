import asyncio
import json
import subprocess
import time
from flask import Flask, render_template, request
from flask_sqlalchemy import SQLAlchemy
import musicpd
from pywizlight import wizlight, PilotBuilder
from apscheduler.schedulers.background import BackgroundScheduler


APP = Flask(__name__)
APP.config.from_json("config.json")
APP.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
DB = SQLAlchemy(APP)

WAKEUP_INT = False

sched = BackgroundScheduler(daemon=True)
for alarm in APP.config['ALARMS']:
    APP.logger.warn("Alarm scheduled: %s", json.dumps(alarm))
    minute='45'
    hour='07'
    day='*'
    month="*"
    day_of_week="*"
    if 'minute' in alarm:
        minute=alarm['minute']
    if 'hour' in alarm:
        hour=alarm['hour']
    if 'day' in alarm:
        day=alarm['day']
    if 'month' in alarm:
        month=alarm['month']
    if 'day_of_week' in alarm:
        day_of_week=alarm['day_of_week']

    sched.add_job(
        lambda: wakeup(),'cron', minute=minute, hour=hour, day=day,
        month=month, day_of_week=day_of_week)
sched.start()


@APP.route('/', methods=['GET', 'POST'])
def index():
    #subprocess.Popen('/usr/bin/xmms2 play', shell=True)
    mpd = musicpd.MPDClient()
    mpd.connect()
    if 'volume' in request.form:
        mpd.setvol(request.form['volume'])
    return render_template("index.html.j2",
        audioVolume=mpd.status()['volume'])

@APP.route('/api', methods=['GET', 'POST'])
def api():
    global WAKEUP_INT
    mpd = musicpd.MPDClient()
    mpd.connect()
    lightbulb = wizlight(APP.config['LIGHTBULB_IP'])
    response = {}
    if request.method == 'POST':
        #do what you gotta do
        WAKEUP_INT = True
        if 'bulb' in request.args and request.args['bulb'] == 'off':
            asyncio.run(lightbulb.turn_off())
        response = {}
        if 'bulb' in request.args \
            and request.args['bulb'] == 'on' \
            and 'brightness' in request.args \
            and 'temperature' in request.args:
            asyncio.run(
                lightbulb.turn_on(
                    PilotBuilder(
                        brightness=int(request.args['brightness']),
                        colortemp=int(request.args['temperature']))))
        response = {}
        if 'mpd' in request.args and request.args['mpd'] == 'off':
            mpd.clear()
    else:
        asyncio.run(lightbulb.updateState())
        response = {
            'volume': mpd.status()['volume'],
            'commands': mpd.commands(),
            'song': mpd.currentsong().get('name', 'None'),
            'brightness': lightbulb.state.get_brightness(),
            'temperature': lightbulb.state.get_colortemp()
        }
    APP.logger.warn("StopFlag/api: %s", str(WAKEUP_INT))
    return json.dumps(response, indent=2)

def wakeup():
    global WAKEUP_INT
    mpd = musicpd.MPDClient()
    mpd.connect()
    WAKEUP_INT = False
    lightbulb = wizlight(APP.config['LIGHTBULB_IP'])

    bright_start = 0
    bright_stop = 255
    temp_start = 2700
    temp_stop = 6500
    old_volume = mpd.status()['volume']

    mpd.clear()
    mpd.setvol(0)
    mpd.add('https://rozhlas.stream/jazz_aac_128.aac')
    mpd.play()
    for i in range(101):
        APP.logger.warn("StopFlag/task: %s", str(WAKEUP_INT))
        if WAKEUP_INT:
            mpd.setvol(old_volume)
            return
        volume=int((i*70)/100+30)
        mpd.setvol(volume)
        APP.logger.warn("volume: %i", volume)
        bright=int((i * (bright_stop - bright_start) ) / 100 + bright_start)
        temp=int((i * (temp_stop - temp_start) ) / 100 + temp_start)
        APP.logger.warn("brightness: %i; temperature: %i", bright, temp)
        asyncio.run(
            lightbulb.turn_on(
                PilotBuilder(
                    brightness=bright,
                    colortemp=temp)))
        time.sleep(6)
