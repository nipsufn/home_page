"""Flask app scheduling/starting/stopping nightlight and radio"""
import asyncio
import json
import time
from flask import Flask, render_template, request, logging
from flask_sqlalchemy import SQLAlchemy
import musicpd
from pywizlight import wizlight, PilotBuilder
from apscheduler.schedulers.background import BackgroundScheduler


APP = Flask(__name__)
APP.logger = logging.create_logger(APP)
APP.config.from_json("config.json")
APP.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
DB = SQLAlchemy(APP)

WAKEUP_INT = False

SCHED = BackgroundScheduler(daemon=True)
def add_alarms():
    """Initialize scheduler with alarms from config"""
    for alarm in APP.config['ALARMS']:
        APP.logger.warning("Alarm scheduled: %s", json.dumps(alarm))
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

        SCHED.add_job(
            lambda: wakeup(),'cron', # pylint: disable=unnecessary-lambda
            minute=minute, hour=hour, day=day,
            month=month, day_of_week=day_of_week)
add_alarms()
SCHED.start()

@APP.route('/', methods=['GET', 'POST'])
def index():
    """Webpage with advanced controls"""
    mpd = musicpd.MPDClient()
    mpd.connect()
    APP.logger.warning("index form: %s", json.dumps(request.form))
    if 'volume' in request.form:
        mpd.setvol(request.form['volume'])
    return render_template("index.html.j2",
        audioVolume=mpd.status()['volume'])

@APP.route('/api', methods=['GET', 'POST'])
def api():
    """Handle API calls"""
    # pylint: disable-next=global-statement
    global WAKEUP_INT
    mpd = musicpd.MPDClient()
    mpd.connect()
    response = {}
    if request.method == 'POST':
        #do what you gotta do
        WAKEUP_INT = True
        if 'bulb' in request.args:
            lightbulb = wizlight(APP.config['LIGHTBULBS'][request.args['bulb']])
            if request.args['op'] == 'off':
                asyncio.run(lightbulb.turn_off())

            if request.args['op'] == 'on' \
                and 'brightness' in request.args:
                if 'temperature' in request.args:
                    asyncio.run(
                        lightbulb.turn_on(
                            PilotBuilder(
                                brightness=int(request.args['brightness']),
                                colortemp=int(request.args['temperature']))))
                if 'rgb' in request.args:
                    asyncio.run(
                        lightbulb.turn_on(
                            PilotBuilder(
                                brightness=int(request.args['brightness']),
                                rgb=tuple(int(request.args['rgb'][i:i+2], 16) for i in (0, 2, 4))
                                )))
                if 'colour' in request.args:
                    colour = (0,0,0)
                    if request.args['colour'] == 'red':
                        colour = (255,0,0)
                    asyncio.run(
                        lightbulb.turn_on(
                            PilotBuilder(
                                brightness=int(request.args['brightness']),
                                rgb=colour)))

        if 'mpd' in request.args and request.args['mpd'] == 'off':
            mpd.clear()
        if 'mpd' in request.args and request.args['mpd'] == 'on':
            mpd.clear()
            mpd.setvol(100)
            mpd.add('https://rozhlas.stream/jazz_aac_128.aac')
            mpd.play()
    else:
        lightbulb = wizlight(APP.config['LIGHTBULBS']['nightstand'])
        asyncio.run(lightbulb.updateState())
        response = {
            'volume': mpd.status()['volume'],
            'commands': mpd.commands(),
            'song': mpd.currentsong().get('name', 'None'),
            'brightness': lightbulb.state.get_brightness(),
            'temperature': lightbulb.state.get_colortemp()
        }
    APP.logger.warning("StopFlag/api: %s", str(WAKEUP_INT))
    return json.dumps(response, indent=2)

def wakeup():
    """Wakeup procedure"""
    # pylint: disable-next=global-statement
    global WAKEUP_INT
    mpd = musicpd.MPDClient()
    mpd.connect()
    WAKEUP_INT = False
    lightbulb = wizlight(APP.config['LIGHTBULBS']['nightstand'])

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
        APP.logger.warning("StopFlag/task: %s", str(WAKEUP_INT))
        if WAKEUP_INT:
            mpd.setvol(old_volume)
            return
        volume=int((i*70)/100+30)
        mpd.setvol(volume)
        APP.logger.warning("volume: %i", volume)
        bright=int((i * (bright_stop - bright_start) ) / 100 + bright_start)
        temp=int((i * (temp_stop - temp_start) ) / 100 + temp_start)
        APP.logger.warning("brightness: %i; temperature: %i", bright, temp)
        asyncio.run(
            lightbulb.turn_on(
                PilotBuilder(
                    brightness=bright,
                    colortemp=temp)))
        time.sleep(6)
