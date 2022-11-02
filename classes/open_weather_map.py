# open_weather_map.py
"""This module queries OpenWeatherMap.org and provides retrieved data
"""
import logging
import multiprocessing
from datetime import datetime, timedelta
import matplotlib
import matplotlib.pyplot as plot
import matplotlib.dates as plotDates
from PIL import Image

from apscheduler.schedulers.blocking import BlockingScheduler
from classes.json_from_api import JSONFromAPI

class OpenWeatherMap(JSONFromAPI):
    """This class queries OpenWeatherMap.org and provides retrieved data
    """
    def __init__(self, location, token):
        """Class constructor
        Args:
            location (str): forecast location, 'City,xx', xx = country code
            token (str): API token
        """
        super().__init__()
        self.logger = logging.getLogger(type(self).__name__)
        self.__location = location
        self.__token = token
        self.json = None
        self.sunrise = ""
        self.sunset = ""
        self._updated = False
        self.__update()
        self.logger.debug('Class initialized')

    def is_day(self) -> bool:
        """check if it's day now"""
        now = datetime.now()
        if (datetime.fromtimestamp(self.sunrise)
                > now
                > datetime.fromtimestamp(self.sunset)):
            return True
        return False

    def is_night(self) -> bool:
        """check if it's night now"""
        return not self.is_day()

    def send_sunset_datetime(self,
            producer_opw: multiprocessing.connection.Connection):
        """send sunset datetime via pipe"""
        self.logger.error("opw: sending sunset")
        producer_opw.send(datetime.fromtimestamp(self.sunset))

    def schedule_at_sunset(self, scheduler: BlockingScheduler,
            function: object, args: dict, flag_master_switch: multiprocessing.sharedctypes.SynchronizedBase, offset: timedelta = timedelta()):
        """send sunset datetime via pipe"""
        when = datetime.fromtimestamp(self.sunset)
        if when < datetime.now():
            offset += timedelta(days=1)
        when += offset
        scheduler.add_job(
            function,
            trigger = 'date',
            args = [args, flag_master_switch],
            run_date=when)
        self.logger.error("Sunset scheduled: %s", when.strftime('%Y-%m-%d %H:%M'))

    def __get_night_timestamps(self, x_axis_timestamps, days=0):
        """Project sunset and sunrise times few days forward
        Args:
            xAxisTimestamps (:list:`int`): list of timestamps that will bound
                                           output
            days (int): number of days that will bound output
        """
        night_timestamps = []
        i = 0
        while True:
            breakout = False
            tmp_sunset = self.sunset + i*86400
            tmp_sunrise = self.sunrise + (i+1)*86400
            sunset = 0
            if x_axis_timestamps[0] < tmp_sunset < x_axis_timestamps[-1]:
                sunset = tmp_sunset
            else:
                if tmp_sunset > x_axis_timestamps[-1]:
                    sunset = x_axis_timestamps[-1]
                    breakout = True
                if tmp_sunset < x_axis_timestamps[0]:
                    sunset = x_axis_timestamps[0]

            sunrise = 0
            if x_axis_timestamps[0] < tmp_sunrise < x_axis_timestamps[-1]:
                sunrise = tmp_sunrise
            else:
                if tmp_sunrise > x_axis_timestamps[-1]:
                    sunrise = x_axis_timestamps[-1]
                    breakout = True
                if tmp_sunrise < x_axis_timestamps[0]:
                    sunrise = x_axis_timestamps[0]

            night_timestamps.append([sunset, sunrise])
            self.logger.info(
                "sunset: %s; sunrise: %s",
                datetime.fromtimestamp(sunset).strftime('%Y-%m-%d %H:%M'),
                datetime.fromtimestamp(sunrise).strftime('%Y-%m-%d %H:%M')
                )
            i += 1
            if breakout or (days != 0 and i > days):
                break
        return night_timestamps

    def __update(self) -> bool:
        """Update forecast data"""
        tmp_url = (
            "http://api.openweathermap.org/data/2.5/forecast?q="
            + self.__location
            + "&APPID="
            + self.__token
            )
        tmp_json = self._get_json_from_url(tmp_url)
        if tmp_json is None:
            return False
        self.json = tmp_json
        self.sunrise = tmp_json['city']['sunrise']
        self.sunset = tmp_json['city']['sunset']
        self._updated = True
        return True

    def update(self,
            producer_opw: multiprocessing.connection.Connection) -> bool:
        """Update and send forecast data"""
        ret = self.__update()
        producer_opw.send({
            'plot': self.plot()
        })
        self.logger.info("sent data via pipe")
        return ret

    def plot(self, x_resolution=420, y_resolution=200, days=0):
        """Generates weather plot containing precipitation and temperature
        Args:
            x_res (int): horizontal length in pixels
            y_res (int): vertical length in pixels
            days (int, optional): number of days to plot
                                  (0 - as much as possible)
        Returns:
            PIL.Image: image containing the plot
        """
        #pylint: disable-msg=too-many-locals

        #process forecast data
        matplotlib.use('Agg')
        forecast_plot_image = Image.new('RGB', (x_resolution, y_resolution),
            (0xFF, 0xFF, 0xFF))

        x_axis_timestamps = []
        x_axis_hours = []
        y_axis_temperature = []
        y_axis_precipitation = []
        for timestamp in self.json['list']:
            self.logger.info(
                "timestamp: %s",
                datetime.fromtimestamp(timestamp['dt']).strftime('%Y-%m-%d %H:%M'))
            x_axis_timestamps.append(timestamp['dt'])
            x_axis_hours.append(datetime.fromtimestamp(timestamp['dt']))
            y_axis_temperature.append(timestamp['main']['temp']-273.15)
            precipitation_tmp = 0
            if 'rain' in timestamp:
                precipitation_tmp += timestamp['rain']['3h']
            if 'snow' in timestamp:
                precipitation_tmp += timestamp['snow']['3h']
            y_axis_precipitation.append(precipitation_tmp)

        temp_n_percip_plot = plot.figure(figsize=(x_resolution/80,
                                                  y_resolution/80),
                                         dpi=80)
        #plot precipitation
        ax1 = temp_n_percip_plot.add_subplot(111)
        ax1.plot(x_axis_hours, y_axis_precipitation, color='black')
        ax1.fill_between(x_axis_hours, 0, y_axis_precipitation, color='black')
        ax1.set_ylim(bottom=0)
        ax1.set_xlim(auto=True)

        #plot temperatures
        ax2 = ax1.twinx()
        ax2.yaxis.tick_left()
        ax2.plot(x_axis_hours, y_axis_temperature, color='red')
        ax2.set_xlim(auto=True)
        ax2.xaxis.set_major_formatter(plotDates.DateFormatter('%H'))
        ax2.xaxis.set_major_locator(
            plotDates.HourLocator(byhour=range(0, 24, 6)))

        #grid lines for temperatures
        ax2.grid(True, 'major', 'y', color="black")

        #mark nights
        for night_timestamp in \
                self.__get_night_timestamps(x_axis_timestamps, days):
            ax2.axvspan(xmin=datetime.fromtimestamp(night_timestamp[0]),
                        xmax=datetime.fromtimestamp(night_timestamp[1]),
                        facecolor="none", edgecolor="black", hatch='....')

        for x_axis_hour in x_axis_hours:
            if x_axis_hour.hour == 1:
                ax2.axvline(x=x_axis_hour-timedelta(hours=1), ls=':',
                            color="red")

        ax1.xaxis.set_minor_formatter(plotDates.DateFormatter('%a'))
        ax1.xaxis.set_minor_locator(plotDates.HourLocator(byhour=11))
        ax1.tick_params(axis='x', which='minor', top=False, labeltop=True,
                        bottom=False, labelbottom=False)
        ax1.yaxis.tick_right()

        #fix margins
        ax1.margins(x=0)
        ax2.margins(x=0)
        plot.margins(x=0)

        #display
        forecast_canvas = temp_n_percip_plot.canvas
        forecast_canvas.draw()
        forecast_plot_image = Image.frombytes(
            'RGB',
            forecast_canvas.get_width_height(),
            forecast_canvas.tostring_rgb())

        #clean up
        plot.close(temp_n_percip_plot)
        self.logger.info('plot generated ')
        return forecast_plot_image
