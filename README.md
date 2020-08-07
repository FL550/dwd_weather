[![GitHub Release][releases-shield]][releases]
[![License][license-shield]](LICENSE)
[![hacs][hacsbadge]](hacs)
<!-- [![Community Forum][forum-shield]][forum] -->

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

<!---->

***

[hacs]: https://github.com/custom-components/hacs
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge
<!-- [forum-shield]: https://img.shields.io/badge/community-forum-brightgreen.svg?style=for-the-badge -->
<!-- [forum]: https://community.home-assistant.io/ -->
[license-shield]: https://img.shields.io/github/license/custom-components/blueprint.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/custom-components/blueprint.svg?style=for-the-badge
[releases]: https://github.com/FL550/dwd_weather/releases
