import asyncio
import json
import subprocess
import time
from flask import Flask, render_template, request
import musicpd
from pywizlight import wizlight, PilotBuilder
from apscheduler.schedulers.background import BackgroundScheduler


APP = Flask(__name__)
APP.config.from_json("config.json")

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
WAKEUP_INT = False

@APP.route('/', methods=['GET', 'POST'])
def index():
    subprocess.Popen('/usr/bin/xmms2 play', shell=True)
    return render_template("index.html.j2", xmms2playing="xmms2playing", xmms2volume="xmms2volume")

@APP.route('/api', methods=['GET', 'POST'])
def api():
    global WAKEUP_INT
    mpdlient = musicpd.MPDClient()
    mpdlient.connect()
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
            mpdlient.clear()
    else:
        asyncio.run(lightbulb.updateState())
        response = {
            'volume': mpdlient.status()['volume'],
            'commands': mpdlient.commands(),
            'song': mpdlient.currentsong().get('name', 'None'),
            'brightness': lightbulb.state.get_brightness(),
            'temperature': lightbulb.state.get_colortemp()
        }
    APP.logger.warn("StopFlag/api: %s", str(WAKEUP_INT))
    return json.dumps(response, indent=2)

def wakeup():
    global WAKEUP_INT
    WAKEUP_INT = False
    mpdlient = musicpd.MPDClient()
    mpdlient.connect()
    lightbulb = wizlight(APP.config['LIGHTBULB_IP'])

    bright_start = 0
    bright_stop = 255
    temp_start = 2700
    temp_stop = 6500

    mpdlient.clear()
    mpdlient.setvol(0)
    mpdlient.add('https://rozhlas.stream/jazz_aac_128.aac')
    mpdlient.play()
    for i in range(101):
        APP.logger.warn("StopFlag/task: %s", str(WAKEUP_INT))
        if WAKEUP_INT:
            mpdlient.setvol(100)
            return
        volume=int((i*70)/100+30)
        mpdlient.setvol(volume)
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
