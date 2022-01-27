#!/usr/bin/env python3
"""Flask app scheduling/starting/stopping nightlight and radio"""

import argparse
from datetime import datetime, timedelta
import logging
import logging.handlers
import multiprocessing

import sys
import json

from apscheduler.schedulers.background import BackgroundScheduler
#from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from flask import Flask, Response, render_template, request, logging as flasklogging
#from flask_sqlalchemy import SQLAlchemy
import musicpd
import serial


from classes.airly import Airly
from classes.c_ro_jazz import CRoJazz
from classes.open_weather_map import OpenWeatherMap
from classes import wizbulb
from classes import wakeup
from classes import eink

app = Flask(__name__)

class PlainTextTcpHandler(logging.handlers.SocketHandler):
    """ Sends plain text log message over TCP channel """
    def makePickle(self, record):
        message = self.formatter.format(record)
        return message.encode()

def mpd(mpd_request: dict,) -> None:
    """handle mpd-related requests"""
    app.producer_wakeup_int.send(True)
    mpd_client = musicpd.MPDClient()
    mpd_client.connect()
    if mpd_request.args['mpd'] == 'off':
        mpd_client.clear()
    if mpd_request.args['mpd'] == 'on':
        mpd_client.clear()
        mpd_client.setvol(100)
        mpd_client.add('https://rozhlas.stream/jazz_aac_128.aac')
        mpd_client.play()
    if mpd_request.args['mpd'] == 'volume' and 'volume' in mpd_request.args:
        app.logger.warning("trying to set volume: %s",
            mpd_request.args['volume'])
        mpd_client.setvol(mpd_request.args['volume'])

@app.route('/', methods=['GET', 'POST'])
def index() -> str:
    """Webpage with advanced controls"""
    mpd_client = musicpd.MPDClient()
    mpd_client.connect()
    app.logger.warning("index form: %s", json.dumps(request.form))
    if 'volume' in request.form:
        mpd_client.setvol(request.form['volume'])
    return render_template("index.html.j2",
        audioVolume=mpd_client.status()['volume'])

@app.route('/api', methods=['GET', 'POST'])
def api() -> Response:
    """Handle API calls"""
    response = {}
    if request.method == 'POST':
        if 'bulb' in request.args:
            wizbulb.set_bulb(request, app.config)
        if 'mpd' in request.args:
            mpd(request)
    else:
        mpd_client = musicpd.MPDClient()
        mpd_client.connect()
        out = wizbulb.get_bulb(app.config)
        response = {
            'volume': mpd_client.status()['volume'],
            'commands': mpd_client.commands(),
            'song': mpd_client.currentsong(),
            'bulbs': out,
        }
    response = Response(json.dumps(response, indent=2),
        200, mimetype='application/json')
    response.headers["Content-Type"] = "application/json; charset=utf-8"
    return response

#scheduled job
def add_alarms(sched: BackgroundScheduler,
        consumer_wakeup_int: multiprocessing.connection.Connection) -> None:
    """Initialize scheduler with alarms from config"""
    for alarm in app.config['ALARMS']:

        minute=alarm['minute']
        hour=alarm['hour']
        day=alarm['day']
        month=alarm['month']
        day_of_week=alarm['day_of_week']

        sched.add_job(
            wakeup.wakeup,
            trigger = 'cron',
            args = [consumer_wakeup_int, app.config],
            minute=minute,
            hour=hour,
            day=day,
            month=month,
            day_of_week=day_of_week)

        app.logger.warning("Alarm scheduled: %s", json.dumps(alarm))

#process
def tcplog(tcplog_consumer: multiprocessing.connection.Connection,
        host: str, port: int) -> None:
    """Send text from pipe to TCP"""
    log = logging.getLogger("tcplog")
    log_handler = PlainTextTcpHandler(host, port)
    log_handler.setFormatter(logging.Formatter('%(message)s'))
    log.addHandler(log_handler)
    while True:
        app.logger.warning("tcplog: consuming")
        log.warning(tcplog_consumer.recv())

#process
def serial_to_log(tcplog_producer:
        multiprocessing.connection.Connection) -> None:
    """Read serial and send to logger"""
    ser = serial.Serial('/dev/ttyUSB0', 115200, timeout=90)
    ser.flushInput()
    while True:
        try:
            ser_out = ser.readline()
            app.logger.warning("serial_to_log: producing")
            tcplog_producer.send(ser_out.decode("utf-8"))
        except serial.serialutil.SerialException:
            exc_type, value, _ = sys.exc_info()
            app.logger.warning("%s: %s", exc_type.__name__, value)

def main():
    """main wrapper"""
    parser = argparse.ArgumentParser()
    parser.add_argument("-l", "--loglevel", type=str,
                        choices=['critical','error','warning','info','debug'],
                        help="set loglevel")
    parser.add_argument("-d", "--debug", "-v", "--verbose", action="store_true",
                        help="debug mode")
    args = parser.parse_args()

    level_str_to_int = {
        'critical': logging.CRITICAL,
        'fatal': logging.FATAL,
        'error': logging.ERROR,
        'warn': logging.WARNING,
        'warning': logging.WARNING,
        'info': logging.INFO,
        'debug': logging.DEBUG,
        'notset': logging.NOTSET,
    }
    if args.loglevel:
        logging.basicConfig(level=level_str_to_int[args.loglevel])
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)

    app.logger = flasklogging.create_logger(app)
    app.config.from_file("config.json", json.load)

    app.cro_jazz = CRoJazz()
    app.open_weather = OpenWeatherMap(
        app.config['FORECAST']['forecastLocation'],
        app.config['FORECAST']['forecastToken']
        )
    app.smog_airly = Airly(
        app.config['FORECAST']['smogLocations'],
        app.config['FORECAST']['smogToken']
        )

    consumer_cro, producer_cro = multiprocessing.Pipe()
    consumer_opw, producer_opw = multiprocessing.Pipe()
    consumer_arl, producer_arl = multiprocessing.Pipe()
    consumer_tcplog, producer_tcplog = multiprocessing.Pipe()
    consumer_wakeup_int, app.producer_wakeup_int = multiprocessing.Pipe()

    #APP.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
    #DB = SQLAlchemy(APP)

    scheduler = BackgroundScheduler(daemon=True)
    scheduler_start = datetime.now()+timedelta(seconds=10)
    scheduler.add_job(
        app.cro_jazz.update,
        trigger = 'interval',
        args = [producer_cro],
        minutes=1,
        start_date=scheduler_start)
    scheduler.add_job(
        app.open_weather.update,
        trigger = 'interval',
        args = [producer_opw],
        hours=1,
        start_date=scheduler_start)
    scheduler.add_job(
        app.smog_airly.update,
        trigger = 'interval',
        args = [producer_arl],
        hours=1,
        start_date=scheduler_start)

    add_alarms(scheduler, consumer_wakeup_int)

    multiprocessing.log_to_stderr()
    tcplog_proc = multiprocessing.Process(target=tcplog,
        args=[consumer_tcplog, '127.0.0.1', 5170])
    tcplog_proc.start()
    serial_proc = multiprocessing.Process(target=serial_to_log,
        args=[producer_tcplog])
    serial_proc.start()
    eink_proc = multiprocessing.Process(target=eink.update_eink,
        args=[consumer_cro, consumer_opw, consumer_arl, producer_tcplog])
    eink_proc.start()

    scheduler.start()
    app.run()

if __name__ == "__main__":
    main()
