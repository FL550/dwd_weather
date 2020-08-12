[![GitHub Release][releases-shield]][releases]
[![License][license-shield]](LICENSE)
[![hacs][hacsbadge]](hacs)
[![Community Forum][forum-shield]][forum]

_DISCLAIMER: This project is a private open source project and doesn't have any connection with Deutscher Wetterdienst._

This integration uses ['simple_dwd_weatherforecast'](https://github.com/FL550/simple_dwd_weatherforecast) to fetch weather data from Deutscher Wetterdienst (DWD). This integration is based on [Open Data](https://www.dwd.de/DE/leistungen/opendata/opendata.html) from DWD and based on their [Licence](https://www.dwd.de/EN/service/copyright/copyright_artikel.html).

# Installation

1. Click install.
1. In the HA UI go to "Configuration" -> "Integrations" click "+" and search for "Deutscher Wetterdienst".
  _You can repeat this for as many stations as you like._
1. Follow the setup instructions.

# Configuration

The configuration is done via UI. If you insert a station_id in the setup dialog, you will override the coordinates and use the specific station_id instead. Possible station_ids can be found [here](https://github.com/FL550/simple_dwd_weatherforecast/blob/master/simple_dwd_weatherforecast/stations.py) if needed.

You can add as many stations as you like. Each will appear as an individual entity in home-assistant. You can add more stations by repeating the second step of the install instructions.

# Additional sensor values

This integration allows you to add a hourly forecast for the next 10 days of the following values:

- Weather condition
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

The sensor values will be set when the next update of dwd_weather is scheduled by HA. This is done every 15 minutes. You can skip the waiting time by restarting HA.

## Help and Contribution

Feel free to open an issue if you find one and I will do my best to help you. If you want to contribute, your help is appreciated! If you want to add a new feature, add a pull request first so we can chat about the details.

## Licenses

This package uses public data from [DWD OpenData](https://www.dwd.de/DE/leistungen/opendata/opendata.html). The Copyright can be viewed [here](https://www.dwd.de/DE/service/copyright/copyright_node.html).

<!---->

***

[hacs]: https://github.com/custom-components/hacs
[hacsbadge]: https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge
[forum-shield]: https://img.shields.io/badge/community-forum-brightgreen.svg?style=for-the-badge
[forum]: https://community.home-assistant.io/t/deutscher-wetterdienst-dwd/217488
[license-shield]: https://img.shields.io/github/license/custom-components/blueprint.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/FL550/dwd_weather.svg?style=for-the-badge
[releases]: https://github.com/FL550/dwd_weather/releases
