[![GitHub Release][releases-shield]][releases]
[![releases][downloads-shield]](releases)
[![License][license-shield]](LICENSE)
[![hacs][hacsbadge]](hacs)
[![Community Forum][forum-shield]][forum]
[![BuyMeCoffee][buymecoffeebadge]][buymecoffee]

_DISCLAIMER: This project is a private open source project and doesn't have any connection with Deutscher Wetterdienst._

This integration uses ['simple_dwd_weatherforecast'](https://github.com/FL550/simple_dwd_weatherforecast) to fetch weather data from Deutscher Wetterdienst (DWD). This integration is based on [Open Data](https://www.dwd.de/DE/leistungen/opendata/opendata.html) from DWD and based on their [Licence](https://www.dwd.de/EN/service/copyright/copyright_artikel.html).

_Please note, that the "current" weather values are not measured values. The values shown are the forecasted values for the actual hour. The forecast itself is updated every 6 hours. If anyone knows a source for actual measurements, please let me know._

# Installation

1. Install integration via HACS.
1. In the HA UI go to "Configuration" -> "Integrations" click "+" and search for "Deutscher Wetterdienst".
   _You can repeat this for as many stations as you like._
1. Follow the setup instructions.

# Configuration

The configuration is done via UI. If you insert a station_id in the setup dialog, you will override the coordinates and use the specific station_id instead. Possible station_ids can be found [here](https://github.com/FL550/simple_dwd_weatherforecast/blob/master/simple_dwd_weatherforecast/stations.py) if needed.

If you like, you can change the interval for the weather forecast during setup of the sensor. For this, you have to enter the desired interval in the relevant field. The interval can't be larger than 24 hours and if you divide 24 by the value, the remainder have to be 0. For example 24 / 6 = 4.0 is fine, 24 / 5 = 4.8 is not.

You can add as many stations as you like. Each will appear as an individual entity in Home Assistant. You can add more stations by repeating the second step of the install instructions.

# Usage

## Lovelace mode

If you followed the previous steps, you should now have a weather entity inside Home Assistant which contains the weather for today and the next 4 days. To display the weather, you can use the default weather-card where you can select the DWD-weather entity you configured earlier. To add the card follow these steps:

1. Go to the view where you would like to a the weather card.
1. Click on the three dots at the top right corner.
1. Select "Edit Dashboard".
1. Click on the round button with the "plus"-symbol.
1. Pick the "Weather Forecast" card.
1. In the following configuration dialog, choose the weather entity you need.
1. If you would like to display the forecast, check the corresponding slider.
1. Per default the info displayed below the current temperature are the temperature extrema for this day. If if would like to change this, you can enter the following in the field "Secondary Info Attribute":
   - `humidity`
   - `pressure`
   - `wind_bearing`
   - `wind_speed`
   - `visibility`
1. Click on "Save" and voila, you have your own DWD weather forecast.
1. Finally if you like my work, I would be very happy if you [buy me a coffee](https://www.buymeacoffee.com/FL550). :)

## YAML mode

If you are not using the graphical interface and want to use the yaml-mode, you can add the card like this:

```yaml
type: weather-forecast
entity: weather.dwd_weather_*station_name*
```

If you would like to change the secondary info, you have to add this line and replace pressure with whatever info you like:

```yaml
secondary_info_attribute: pressure
```

## Weather report

If you want to get the regional weather report as text, you have to enable the _weather_report_ sensor. For instructions on this see below at [Additional sensor values](Additional-sensor-values). You can then include the report in a markdown card. For this, you have to add the following template to the content field where you replace the part after _sensor._ with your weather station:

```yaml
{{ state_attr("sensor.weather_report_homburg_bad", "data") }}
```

To find the correct name for the configured station, have a look at the developer tools within Home Assistant.

## Additional sensor values

### These are only needed when you want hourly data or the weather report. Daily values are included in the weather entity!

This integration allows you to add a hourly forecast for the next 10 days of the following values:

- Weather condition
- Weather report as text
- Temperature
- Dewpoint
- Pressure
- Wind Speed
- Wind Direction
- Wind Gusts
- Precipitation
- Precipitation Probability
- Precipitation Duration
- Cloud Coverage
- Visibility
- Sun Duration
- Sun Irradiance
- Fog Probability
- Humidity

The sensors are disabled per default, as they contain a lot of data.

You can enable the ones you like in HA UI under "Configuration" -> "Entities" -> click on the filter icon on the right -> Check "Show diabled entities" -> Check the ones you like to enable -> Click "ENABLE SELECTED" at the top -> Confirm the next dialog

The sensor values will be set when the next update of dwd_weather is scheduled by Home Assistant. This is done every 15 minutes. You can skip the waiting time by restarting HA.

## Help and Contribution

Feel free to open an issue if you find one and I will do my best to help you. If you want to contribute, your help is appreciated! If you want to add a new feature, add a pull request first so we can chat about the details.

## Licenses

This package uses public data from [DWD OpenData](https://www.dwd.de/DE/leistungen/opendata/opendata.html). The Copyright can be viewed [here](https://www.dwd.de/DE/service/copyright/copyright_node.html).

<!---->

---

[hacs]: https://github.com/custom-components/hacs
[hacsbadge]: https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge
[forum-shield]: https://img.shields.io/badge/community-forum-brightgreen.svg?style=for-the-badge
[forum]: https://community.home-assistant.io/t/deutscher-wetterdienst-dwd/217488
[license-shield]: https://img.shields.io/github/license/custom-components/blueprint.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/FL550/dwd_weather.svg?style=for-the-badge
[releases]: https://github.com/FL550/dwd_weather/releases
[downloads-shield]: https://img.shields.io/github/downloads/FL550/dwd_weather/total.svg?style=for-the-badge
[buymecoffee]: https://www.buymeacoffee.com/FL550
[buymecoffeebadge]: https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow?style=for-the-badge
