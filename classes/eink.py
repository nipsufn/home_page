# eink.py
"""This module wraps e-ink update funcion
"""
from datetime import datetime
import json
import logging
import multiprocessing
import time

from PIL import Image, ImageDraw, ImageFont

from classes.epd7in5b import Epd

__logger = logging.getLogger(__name__)
__log_handler = logging.StreamHandler()
__log_handler.setFormatter(
    logging.Formatter(
        '[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
        )
    )
__logger.addHandler(__log_handler)

#process
def update_eink(consumer_cro: multiprocessing.connection.Connection,
        consumer_opw: multiprocessing.connection.Connection,
        consumer_arl: multiprocessing.connection.Connection,
        producer_tcplog: multiprocessing.connection.Connection) -> None:
    """update e-ink display"""
    epd = Epd()
    epd.init()
    epd.clear("white")
    startup_lock = True
    while True:
        if startup_lock:
            __logger.debug("update_eink: waiting for cro")
            while not consumer_cro.poll():
                pass
            __logger.debug("update_eink: waiting for arl")
            while not consumer_arl.poll():
                pass
            __logger.debug("update_eink: waiting for opw")
            while not consumer_opw.poll():
                pass
            startup_lock = False

        update_display = False

        if consumer_cro.poll():
            # here assing cro data
            cro_jazz = consumer_cro.recv()
            if cro_jazz['updated']:
                update_display = True
            __logger.debug('from pipe: %s', cro_jazz)
        # those are updated infrequently, no point spamming APIs
        if consumer_arl.poll():
            # here assing cro data
            smog_airly = consumer_arl.recv()
            __logger.debug('from pipe: %s', smog_airly)
            if smog_airly['updated']:
                update_display = True
            if smog_airly['updated']:
                smog_json = json.dumps({
                        "severity": "notice",
                        "pm10_outside": smog_airly['pm001'],
                        "pm25_outside": smog_airly['pm025'],
                        "pm100_outside": smog_airly['pm100'],
                        "temp_outside": smog_airly['temp'],
                        "humi_outside": smog_airly['humi'],
                        "press_outside": smog_airly['press']
                    }) + '\n'
                __logger.debug("update_eink: producing")
                producer_tcplog.send(smog_json)
            update_display = True

        if consumer_opw.poll():
            forecast_plot_image = consumer_opw.recv()['plot']
            __logger.debug('from pipe: image')
            update_display = True

        if update_display:

            framebuffer_font_big = ImageFont.truetype(
                'SourceCodePro-Regular.ttf', 40)
            framebuffer_font_small = ImageFont.truetype(
                'SourceCodePro-Regular.ttf', 12)

            framebuffer_image = Image.new('RGB', (385, 640), (0xFF, 0xFF, 0xFF))
            framebuffer_image.paste(forecast_plot_image, (-20, 430))
            framebuffer_draw = ImageDraw.Draw(framebuffer_image)
            framebuffer_draw.text((10, 0),
                                datetime.now().strftime('%Y-%m-%d'),
                                font=framebuffer_font_big, fill=0)

            #todo: only if crojazz is playing
            top_offset = 45
            text_line = ('ČRoJazz: ' + cro_jazz['track_artist'] + " - "
                        + cro_jazz['track_title'])
            framebuffer_draw.text((10, top_offset+16), text_line,
                                font=framebuffer_font_small, fill=0)

            text_line = ('Smog:    ' + str(smog_airly['pm001']) + "/"
                        + str(smog_airly['pm025']) + "/"
                        + str(smog_airly['pm100']))

            dust_string_color = (0, 0, 0) if smog_airly['is_air_ok'] else (255, 0, 0)
            framebuffer_draw.text((10, top_offset+16*2), text_line,
                                font=framebuffer_font_small,
                                fill=dust_string_color)
            text_line = 'Temp:    '+str(smog_airly['temp'])+"°"
            framebuffer_draw.text((10, top_offset+16*3), text_line,
                                font=framebuffer_font_small, fill=0)

            # sanitize image palette
            framebuffer_image = framebuffer_image.quantize(
                palette=Image.open('palette_bwr_bodge.bmp'))

            framebuffer_image = framebuffer_image.rotate(90, expand=True)
            epd.display(framebuffer_image)
            __logger.info("display updated")
        time.sleep(60)
