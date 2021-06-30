## Contributing to Map'A'Droid
***************************

The following summarizes the process for contributing changes.

Map'A'Droid utilizes `make` to build a consistent development environment across platforms. This helps ensure that any changes made pass required unit-tests and can identify regressions. To utilize `make` the following requirements need to be met:

 * Make
 * pip
 * pre-commit
 * docker
 * docker-compose
 * Python

Some of the dependencies will give additional information if its not installed.
**************

## Make Commands

The following `make` commands are available:

 * `setup` - Install pre-commit and install the required git hooks. This should be run whenever new hooks are added (should be rare since most will be handled by pre-commit).
 * `clean` - Stop containers related to MAD development and cleanup ./tox folder
 * `build` - Multi-stage docker build. Build the MAD base image (local_mad_production) and build the development image (local_mad_development) without using the cache
 * `rebuild` - Same as `build` but can re-use cache
 * `up` - Start MariaDB and local_mad_development containers. MariaDB container does not have a persistent volume
 * `down` - Execute MariaDB and local_mad_development containers
 * `shell` - Execute `up` and gives user-level access to local_mad_development container
 * `root-shell` - Execute `up` and gives root-level access to local_mad_development container
 * `run` - Start MariaDB and local_mad_development containers. MariaDB container has a persistent volume
 * `tests` - Execute `up` and run all tests through tox
 * `unittests` - Execute `up` and run tox tests for py37
 * `shell-<pyxx>` - Execute `up` and grant user-level access with the tox virtual environment selected. Including `RECREATE=1` will rebuild the tox environment
 * `versions` - Lookup the current version for pip, pre-commit, docker, and docker-compose
**************


## Packages roughly explained
```
.
├── cache -> Definition for caching classes/services used
├── db -> Anything in regards to DB access and model definitions (i.e. table definitions)
│   ├── helper -> Helpers to query the DB. A class per table.
│   └── resource_definitions -> Definitions of tables adding comments to render madmin pages. Planned to be replaced by using the table definitions directly.
├── geofence -> Geofence-related calculations/GeofenceHelper
├── mad_apk -> Wizard and APK storage (filesystem, DB) in order to maintain APK files that can be installed on devices
├── madmin
│   └── endpoints -> folder containing all endpoints of MADmin (i.e. a class per route)
│       ├── api -> "/api/..."
│       │   ├── apks
│       │   ├── autoconf
│       │   └── resources
│       └── routes
│           ├── apk
│           ├── autoconfig
│           ├── control
│           ├── event
│           ├── map
│           ├── misc
│           ├── settings
│           └── statistics
├── mapping_manager -> MappingManager basically is a central component of MAD. All routemanagers and configurations are loaded here and queried by workers.
├── mitm_receiver -> MITMReceiver receives data of Pogo (endpoint configured in PogoDroid), provides endpoints for autoconf and provides settings/details about the mode the worker/device should scan with
│   └── endpoints
│       ├── autoconfig
│       └── mad_apk
├── ocr -> OCR related functionality to detect certain windows and handle situations
├── patcher -> DB migrations
├── plugins -> Plugins allow for ANY code to be executed at startup to provide additional functionality to MAD
│   └── endpoints -> The endpoints relevant for plugins are loaded as AIOHTTP sub-applications. Thus plugins are provided by a sub-application, each plugin is then served with an additional sub-application (if needed)
├── route -> Routemanagers for all the modes supported by MAD. The base class RouteManagerBase provides the core logic. Template Method was used here since the core logic of routemanagers is pretty much the same: calculate routes, maintain a priority queue (optional) and provide locations to workers upon request.
│   └── routecalc -> Clustering and route calculation algorithms - TSP being the biggest enemy ;)
├── tests -> Unit tests likely broken since those are of times before asyncio was introduced -> needs fixing
│   ├── api
│   └── mad_apk
├── utils -> Utility classes/methods as well as the DeviceUpdater class dealing with MADmin jobs
├── webhook -> WebhookWorker querying the DB for changes to send changes detected towards the configured endpoints
├── websocket -> All devices using RGC connect to the WebsocketServer which allows communication (back and forth), thus screenshots can be queried, clicks/swipes executed, location adjustments etc.
└── worker -> Each device is represented by a Worker. Template Method was used given Workers are relatively straight forward: Check everything is fine (if not, handle accordingly), teleport/walk to location, do something, repeat.
```