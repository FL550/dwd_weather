<!-- [![GitHub Release][releases-shield]][releases] -->
[![License][license-shield]](LICENSE)
[![hacs][hacsbadge]](hacs)
<!-- [![Community Forum][forum-shield]][forum] -->

{% if prerelease %}
### NB!: This is a Beta version! Please report any errors and bugs!
{% endif %}

{% if not installed %}
## Installation

1. Click install.
1. In the HA UI go to "Configuration" -> "Integrations" click "+" and search for "Deutscher Wetterdienst".
1. Change the coordinates to your needs or insert a station_id directly. This will override the search for the nearest station.

{% endif %}

## Configuration is done in the UI

station_ids can be found [here](https://github.com/FL550/simple_dwd_weatherforecast/blob/master/simple_dwd_weatherforecast/stations.py) if needed. For further infos about the usage and reporting issuesplease visit GITHUB
<!-- TODO Github URL -->
<!---->

***

[hacs]: https://github.com/custom-components/hacs
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge
<!-- [forum-shield]: https://img.shields.io/badge/community-forum-brightgreen.svg?style=for-the-badge -->
<!-- [forum]: https://community.home-assistant.io/ -->
[license-shield]: https://img.shields.io/github/license/custom-components/blueprint.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/custom-components/blueprint.svg?style=for-the-badge
<!-- [releases]: https://github.com/custom-components/blueprint/releases -->
