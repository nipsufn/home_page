#!/usr/bin/env python3
"""Flask app scheduling/starting/stopping nightlight and radio"""

import argparse
from datetime import datetime, timedelta
import logging
import logging.handlers
import multiprocessing
from multiprocessing.sharedctypes import SynchronizedBase
import sys
import json

from apscheduler.schedulers.background import BackgroundScheduler
#from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from flask import Flask, Response, render_template, request
#from flask_sqlalchemy import SQLAlchemy
import musicpd
import serial


from classes.airly import Airly
from classes.c_ro_jazz import CRoJazz
from classes.open_weather_map import OpenWeatherMap
from classes import wizbulb
from classes import routines
from classes import eink

app = Flask(__name__)

def prepare_logger(args) -> None:
    """create global logger"""

    level = logging.WARNING

    level_str_to_int = {
        'critical': logging.CRITICAL,
        'fatal': logging.FATAL,
        'error': logging.ERROR,
        'warn': logging.WARNING,
        'warning': logging.WARNING,
        'info': logging.INFO,
        'debug': logging.DEBUG,
    }
    if args.loglevel:
        level=level_str_to_int[args.loglevel]
    if args.trace:
        level = logging.DEBUG
    if args.debug:
        level=logging.INFO

    logging.basicConfig(format='[%(asctime)s] %(levelname)s - %(processName)s/%(threadName)s - '
        '%(pathname)s:%(lineno)d - %(name)s - %(message)s', level=level)

def wrap_in_process(func, *args) -> None:
    """wrap passed function in separate process"""
    proc = multiprocessing.Process(target=func,
        args=args)
    proc.start()

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
        #mpd_client.setvol(100)
        mpd_client.add('https://rozhlas.stream/jazz_aac_128.aac')
        mpd_client.play()
    if mpd_request.args['mpd'] == 'volume' and 'volume' in mpd_request.args:
        app.logger.error("trying to set volume: %s",
            mpd_request.args['volume'])
        mpd_client.setvol(mpd_request.args['volume'])

@app.route('/', methods=['GET', 'POST'])
def index() -> str:
    """Webpage with advanced controls"""
    mpd_client = musicpd.MPDClient()
    mpd_client.connect()
    app.logger.error("index form: %s", json.dumps(request.form))
    if 'volume' in request.form:
        mpd_client.setvol(request.form['volume'])
    return render_template("index.html.j2",
        audioVolume=mpd_client.status()['volume'])

@app.route('/api', methods=['GET', 'POST'])
async def api() -> Response:
    """Handle API calls"""
    response = {}
    if request.method == 'POST':
        app.logger.error(json.dumps(request.args))
        if 'bulb' in request.args:
            wrap_in_process(wizbulb.set_bulb_sync, request, app.config)
        if 'mpd' in request.args:
            mpd(request)
    else:
        mpd_client = musicpd.MPDClient()
        mpd_client.connect()
        out = await wizbulb.get_bulb(app.config)
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
        consumer_wakeup_int: multiprocessing.connection.Connection,
        flag_master_switch: SynchronizedBase) -> None:
    """Initialize scheduler with alarms from config"""
    for alarm in app.config['ALARMS']:

        minute=alarm['minute']
        hour=alarm['hour']
        day=alarm['day']
        month=alarm['month']
        day_of_week=alarm['day_of_week']

        sched.add_job(
            routines.wakeup,
            trigger = 'cron',
            args = [consumer_wakeup_int, app.config, flag_master_switch],
            minute=minute,
            hour=hour,
            day=day,
            month=month,
            day_of_week=day_of_week)

        app.logger.error("Alarm scheduled: %s", json.dumps(alarm))

#process
def tcplog(tcplog_consumer: multiprocessing.connection.Connection,
        host: str, port: int) -> None:
    """Send text from pipe to TCP"""
    log = logging.getLogger("tcplog")
    log_handler = PlainTextTcpHandler(host, port)
    log_handler.setFormatter(logging.Formatter('%(message)s'))
    for handler in log.handlers:
        log.removeHandler(handler)
    log.addHandler(log_handler)
    log.propagate = False
    app.logger.warning("tcplog: starting loop")
    while True:
        app.logger.info("tcplog: consuming")
        log.error(tcplog_consumer.recv())

#process
def serial_to_log(tcplog_producer:
        multiprocessing.connection.Connection) -> None:
    """Read serial and send to logger"""
    ser = serial.Serial('/dev/ttyUSB0', 115200, timeout=90)
    ser.flushInput()
    app.logger.warning("serial_to_log: starting loop")
    while True:
        try:
            ser_out = ser.readline()
            app.logger.info("serial_to_log: producing")
            tcplog_producer.send(ser_out.decode("utf-8"))
        except serial.serialutil.SerialException:
            exc_type, value, _ = sys.exc_info()
            app.logger.debug("Serial error: %s: %s", exc_type.__name__, value)

def main():
    """main wrapper"""
    parser = argparse.ArgumentParser()
    parser.add_argument("-l", "--loglevel", type=str,
                        choices=['critical','error','warning','info','debug', 'trace'],
                        help="set loglevel")
    parser.add_argument("-d", "--debug", "-v", "--verbose", action="store_true",
                        help="debug mode")
    parser.add_argument("-dd", "--trace", "-vv", action="store_true",
                        help="debug mode")
    args = parser.parse_args()

    prepare_logger(args)

    app.logger = logging.getLogger("home_page")
    multiprocessing.log_to_stderr()
    log_handler = logging.StreamHandler()
    log_handler.setFormatter(
        logging.Formatter('[%(asctime)s] %(levelname)s - %(processName)s/%(threadName)s - '
            '%(pathname)s:%(lineno)d - %(name)s - %(message)s')
        )

    app.config.from_file("config.json", json.load)
    #multiproc_logger = multiprocessing.get_logger()
    #for handler in multiproc_logger.handlers:
    #    multiproc_logger.removeHandler(handler)
    #multiproc_logger.addHandler(log_handler)

    app.cro_jazz = CRoJazz()
    app.open_weather = OpenWeatherMap(
        app.config['FORECAST']['forecastLocation'],
        app.config['FORECAST']['forecastToken']
        )
    app.smog_airly = Airly(
        app.config['FORECAST']['smogLocations'],
        app.config['FORECAST']['airlyToken']
        )

    app.flag_radio_playing = multiprocessing.Value('i', 1)
    app.flag_master_switch = multiprocessing.Value('i', 1)
    consumer_cro, producer_cro = multiprocessing.Pipe()
    consumer_opw, producer_opw = multiprocessing.Pipe()
    consumer_arl, producer_arl = multiprocessing.Pipe()
    consumer_tcplog, producer_tcplog = multiprocessing.Pipe()
    consumer_wakeup_int, app.producer_wakeup_int = multiprocessing.Pipe()

    #APP.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
    #DB = SQLAlchemy(APP)
    scheduler = BackgroundScheduler()
    scheduler_start = datetime.now()+timedelta(seconds=30)
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
    scheduler.add_job(
        app.open_weather.schedule_at_sunset,
        trigger = 'cron',
        args = [
            scheduler,
            routines.sunset,
            app.config,
            app.flag_master_switch,
            timedelta(minutes=-30)
            ],
        hour="15")

    add_alarms(scheduler, consumer_wakeup_int, app.flag_master_switch)

    wrap_in_process(tcplog, consumer_tcplog, '127.0.0.1', 5170)
    wrap_in_process(serial_to_log, producer_tcplog)
    #polling bulp with ping is unreliable :/
    #wrap_in_process(routines.bulbs_state, app.config, app.flag_master_switch)
    wrap_in_process(
        eink.update_eink,
        consumer_cro,
        consumer_opw,
        consumer_arl,
        producer_tcplog,
        app.flag_radio_playing
        )

    scheduler.start()
    app.run()

if __name__ == "__main__":
    main()
