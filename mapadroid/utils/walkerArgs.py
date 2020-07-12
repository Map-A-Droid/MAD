import os
import sys
from time import strftime

import configargparse
import mapadroid


def memoize(function):
    memo = {}

    def wrapper(*args):
        if args in memo:
            return memo[args]
        else:
            rv = function(*args)
            memo[args] = rv
            return rv

    return wrapper


@memoize
def parseArgs():
    defaultconfigfiles = []
    default_tokenfile = None
    if '-cf' not in sys.argv and '--config' not in sys.argv:
        defaultconfigfiles = [os.getenv('MAD_CONFIG', os.path.join(
            mapadroid.MAD_ROOT, 'configs/config.ini'))]
    if '-td' not in sys.argv and '--token_dispenser' not in sys.argv:
        default_tokenfile = os.getenv('MAD_CONFIG', os.path.join(
            mapadroid.MAD_ROOT, 'configs/token-dispensers.ini'))
    parser = configargparse.ArgParser(
        default_config_files=defaultconfigfiles,
        auto_env_var_prefix='THERAIDMAPPER_')
    parser.add_argument('-cf', '--config',
                        is_config_file=True, help='Set configuration file')
    parser.add_argument('-mf', '--mappings',
                        default=os.getenv('MAD_CONFIG', os.path.join(mapadroid.MAD_ROOT,
                                                                     'configs/mappings.json')),
                        help='Set mappings file')
    parser.add_argument('-asi', '--apk_storage_interface', default='fs', help='APK Storage Interface')

    # MySQL
    parser.add_argument('-dbm', '--db_method', required=False, default="rm",
                        help='LEGACY: DB scheme to be used')
    parser.add_argument('-dbip', '--dbip', required=False,
                        help='IP of MySql Server.')
    parser.add_argument('-dbuser', '--dbusername', required=False,
                        help='Username of MySql Server.')
    parser.add_argument('-dbpassw', '--dbpassword', required=False,
                        help='Password of MySql Server.')
    parser.add_argument('-dbname', '--dbname', required=False,
                        help='Name of MySql Database.')
    parser.add_argument('-dbport', '--dbport', type=int, default=3306,
                        help='Port of MySql Server.')
    parser.add_argument('-dbps', '--db_poolsize', type=int, default=2,
                        help='Size of MySQL pool (open connections to DB). Default: 2.')

    # MITM Receiver
    parser.add_argument('-mrip', '--mitmreceiver_ip', required=False, default="0.0.0.0", type=str,
                        help='IP to listen on for proto data (MITM data). Default: 0.0.0.0 (every interface).')
    parser.add_argument('-mrport', '--mitmreceiver_port', required=False, default=8000,
                        help='Port to listen on for proto data (MITM data). Default: 8000.')
    parser.add_argument('-mrdw', '--mitmreceiver_data_workers', type=int, default=2,
                        help='Amount of workers to work off the data that queues up. Default: 2.')

    # WEBSOCKET
    parser.add_argument('-wsip', '--ws_ip', required=False, default="0.0.0.0", type=str,
                        help='IP for websockt to listen on. Default: 0.0.0.0')
    parser.add_argument('-wsport', '--ws_port', required=False, type=int, default=8080,
                        help='Port of the websocket to listen on. Default: 8080')
    parser.add_argument('-wsct', '--websocket_command_timeout', required=False, type=int, default=30,
                        help='The max time to wait for a command to return (in seconds). Default: 30 seconds.')

    # Walk Settings
    parser.add_argument('-psd', '--post_screenshot_delay', required=False, type=float, default=0.2,
                        help=(
                            'The delay in seconds to wait after taking a screenshot to copy it and start the next '
                            'round. Default: 0.2'))
    parser.add_argument('--initial_restart', default=True,
                        help='Option to enable/disable the initial Pogo restart when scanner starts')
    # TODO: move to area mappings
    parser.add_argument('-dah', '--delay_after_hatch', required=False, type=float, default=3.5,
                        help=(
                            'The delay in minutes to wait after an egg has hatched to move to the location of the '
                            'gym. Default: 3.5'))
    parser.add_argument('--enable_worker_specific_extra_start_stop_handling', default=False,
                        help='Option to enable/disable extra handling for the start/stop routine of workers')
    parser.add_argument('-mvd', '--maximum_valid_distance', required=False, type=int, default=50,
                        help='The maximum distance for a scan of a location to be considered a valid/correct scan of'
                             ' that location in meters. Default: 50m.')

    # job processor
    parser.add_argument('-jobdtwh', '--job_dt_wh', action='store_true', default=False,
                        help='Send job status to discord')
    parser.add_argument('-jobdtwhurl', '--job_dt_wh_url', required=False, default="", type=str,
                        help='Discord Webhook URL for job messages')
    parser.add_argument('-jobdtsdtyp', '--job_dt_send_type', required=False,
                        default="SUCCESS|FAILURE|NOCONNECT|TERMINATED",
                        type=str, help='Kind of Job Messages to send - separated by pipe | '
                                       '(Default: SUCCESS|FAILURE|NOCONNECT|TERMINATED)')
    parser.add_argument('-jobrtnc', '--job_restart_notconnect', required=False, type=int, default=0,
                        help='Restart job if device is not connected (in minutes). Default: 0 (Off)')

    # Runtypes
    parser.add_argument('-os', '--only_scan', action='store_true', default=True,
                        help='Use this instance only for scanning.')
    parser.add_argument('-otc', '--ocr_thread_count', type=int, default=2,
                        help='Amount of threads/processes to be used for screenshot-analysis.')
    parser.add_argument('-wm', '--with_madmin', action='store_true', default=False,
                        help='Start madmin as instance.')
    parser.add_argument('-or', '--only_routes', action='store_true', default=False,
                        help='Only calculate routes, then exit the program. No scanning.')
    parser.add_argument('-cm', '--config_mode', action='store_true', default=False,
                        help='Run in ConfigMode')

    # folder
    parser.add_argument('-tmp', '--temp_path', default='temp',
                        help='Temp Folder for OCR Scanning. Default: temp')

    parser.add_argument('-upload', '--upload_path', default=os.path.join(mapadroid.MAD_ROOT, 'upload'),
                        help='Path for uploaded Files via madmin and for device installation. Default: '
                             '/absolute/path/to/upload')

    parser.add_argument('-pgasset', '--pogoasset', required=False,
                        help=('Path to Pogo Asset.'
                              'See https://github.com/ZeChrales/PogoAssets/'))

    # div. settings

    parser.add_argument('-L', '--language', default='en',
                        help=('Set Language for MadMin / Quests. Default: en'))

    parser.add_argument('-hlat', '--home_lat', default='0.0', type=float,
                        help=('Set Lat from the center of your scan location.'
                              'Especially for using MADBOT (User submitted Raidscreens). Default: 0.0'))
    parser.add_argument('-hlng', '--home_lng', default='0.0', type=float,
                        help=('Set Lng from the center of your scan location.'
                              'Especially for using MADBOT (User submitted Raidscreens). Default: 0.0'))

    parser.add_argument('-gdv', '--gym_detection_value', default='0.75', type=float,
                        help=(
                            'Value of gym detection. The higher the more accurate is checked. 0.65 maybe generate '
                            'more false positive. Default: 0.75'))

    parser.add_argument('-lc', '--last_scanned', action='store_true', default=False,
                        help='Submit last scanned location to RM DB (if supported). Default: False')

    parser.add_argument('-gsd', '--gym_scan_distance', type=float, default=6.0,
                        help='Search for nearby Gmy within this radius (in KM!!). '
                             'In areas with many Gyms reduce this argument to 1-2 Default: 6')

    parser.add_argument('-npmf', '--npmFrom', type=float, default=0.8,
                        help='Matching zoom start value for mon! (Based on resolution)')
    parser.add_argument('-npmv', '--npmValue', type=float, default=2.0,
                        help='Matching zoom max value for mon! (Based on resolution)')

    parser.add_argument('-npv', '--npValue', type=float, default=0.5,
                        help='Matching zoom max value. (Based on resolution)')

    parser.add_argument('-npf', '--npFrom', type=float, default=0.2,
                        help='Matching zoom start value. (Based on resolution)')

    parser.add_argument('-mspass', '--mitm_status_password', default='',
                        help='Header Authorization password for MITM /status/ page')

    # Cleanup Hash Database
    parser.add_argument('-chd', '--clean_hash_database', action='store_true', default=False,
                        help='Cleanup the hashing database.')

    # rarity
    parser.add_argument('-rh', '--rarity_hours', type=int, default=72,
                        help='Set the number of hours for the calculation of pokemon rarity (Default: 72)')
    parser.add_argument('-ruf', '--rarity_update_frequency', type=int, default=60,
                        help='Update frequency for dynamic rarity in minutes (Default: 60)')
    # webhook
    parser.add_argument('-wh', '--webhook', action='store_true', default=False,
                        help='Activate webhook support')
    parser.add_argument('-whurl', '--webhook_url', default='',
                        help='URL endpoint/s for webhooks (seperated by commas) with [<type>] '
                             'for restriction like [mon|weather|raid]http://example.org/foo/bar '
                             '- urls have to start with http*')

    parser.add_argument('-whea', '--webhook_excluded_areas', default="",
                        help='Comma-separated list of area names to exclude elements from within to be sent to a '
                             'webhook')
    parser.add_argument('-pwh', '--pokemon_webhook', action='store_true', default=False,
                        help='Activate pokemon webhook support')
    parser.add_argument('-pwhn', '--pokemon_webhook_nonivs', action='store_true', default=False,
                        help='Send non-IVd pokemon even if they are on Global Mon List')
    parser.add_argument('-swh', '--pokestop_webhook', action='store_true', default=False,
                        help='Activate pokestop webhook support')
    parser.add_argument('-wwh', '--weather_webhook', action='store_true', default=False,
                        help='Activate weather webhook support')
    parser.add_argument('-qwh', '--quest_webhook', action='store_true', default=False,
                        help='Activate quest webhook support')
    parser.add_argument('-qwhf', '--quest_webhook_flavor', choices=['default', 'poracle'], default='default',
                        help='Webhook format for Quests: default or poracle compatible')
    parser.add_argument('-gwh', '--gym_webhook', action='store_true', default=False,
                        help='Activate gym webhook support')
    parser.add_argument('-whser', '--webhook_submit_exraids', action='store_true', default=False,
                        help='Send Ex-raids to the webhook if detected')
    parser.add_argument('-whst', '--webhook_start_time', default=0,
                        help='Debug: Set initial timestamp to fetch changed elements from the DB to send via WH.')
    parser.add_argument('-whmps', '--webhook_max_payload_size', default=0, type=int,
                        help='Split up the payload into chunks and send multiple requests. Default: 0 (unlimited)')
    # weather
    parser.add_argument('-w', '--weather', action='store_true', default=False,
                        help='Read weather and post to db - if supported! (Default: False)')

    # folder
    parser.add_argument('--file_path',
                        help='Defines directory to save worker stats- and position files and calculated routes',
                        default='files')

    # Statistics
    parser.add_argument('-stco', '--stat_gc', action='store_true', default=False,
                        help='Store collected objects (garbage collector) (Default: False)')
    parser.add_argument('-stiv', '--statistic_interval', default=60, type=int,
                        help='Store new local stats every N seconds (Default: 60)')
    parser.add_argument('-stat', '--statistic', action='store_true', default=False,
                        help='Activate system statistics (Default: False)')

    # MADmin
    parser.add_argument('-mmt', '--madmin_time', default='24',
                        help='MADmin clock format (12/24) (Default: 24)')

    parser.add_argument('-mmsc', '--madmin_sort', default='6',
                        help='MADmin sort column Raid/Gym (5= Modify / 6 = Create) (Default: 6)')

    parser.add_argument('-mmip', '--madmin_ip', default='0.0.0.0',
                        help='MADmin listening interface (Default: 0.0.0.0)')
    parser.add_argument('-mmprt', '--madmin_port', default='5000',
                        help='MADmin web port (Default: 5000)')

    parser.add_argument('-mmnrsp', '--madmin_noresponsive', action='store_false', default=True,
                        help='MADmin deactivate responsive tables')

    parser.add_argument('-mmuser', '--madmin_user', default='',
                        help='Username for MADmin Frontend.')

    parser.add_argument('-mmpassword', '--madmin_password', default='',
                        help='Password for MADmin Frontend.')

    parser.add_argument('-mmbp', '--madmin_base_path', default='/',
                        help='Base path for madmin')

    parser.add_argument('-pfile', '--position_file', default='current',
                        help='Filename for bot\'s current position (Default: current)')

    parser.add_argument('-ugd', '--unknown_gym_distance', default='10',
                        help='Show matchable gyms for unknwon with this radius (in km!) (Default: 10)')

    parser.add_argument('-qpub', '--quests_public', action='store_true', default=False,
                        help='Enables MADmin /quests_pub endpoint for public quests overview')

    parser.add_argument('--geofence_file_path',
                        help='Defines directory to save created madmin map geofence files',
                        default='configs/geofences')

    parser.add_argument('-jtc', '--job_thread_count', type=int, default=2,
                        help='Amount of threads to work off the device jobs. Default: 2.')

    parser.add_argument('-ods', '--outdated_spawnpoints', type=int, default=3,
                        help='Define when a spawnpoint is out of date (in days). Default: 3.')

    # etc

    parser.add_argument('-rdt', '--raid_time', default='45', type=int,
                        help='Raid Battle time in minutes. (Default: 45)')
    parser.add_argument('-advcfg', '--advanced_config', default=True, type=bool,
                        help='Basically unusued: enables additional information to be modified when working with areas')

    parser.add_argument('-ld', '--lure_duration', default='30', type=int,
                        help='Lure duration in minutes. (Default: 30)')

    # stats

    parser.add_argument('-ggs', '--game_stats', action='store_true', default=False,
                        help='Generate worker stats')

    parser.add_argument('-ggrs', '--game_stats_raw', action='store_true', default=False,
                        help='Generate worker raw stats (only with --game_stats)')

    parser.add_argument('-gsst', '--game_stats_save_time', default=300, type=int,
                        help='Number of seconds until worker information is saved to database')

    parser.add_argument('-rds', '--raw_delete_shiny', default=0,
                        help='Delete shiny mon in raw stats older then x days (0 =  Disable (Default))')

    parser.add_argument('--quest_stats_fences', default="",
                        help="Comma separated list of geofences for stop/quest statistics (Empty: all)")

    # adb
    parser.add_argument('-adb', '--use_adb', action='store_true', default=False,
                        help='Use ADB for "device control" (Default: False)')
    parser.add_argument('-adbservip', '--adb_server_ip', default='127.0.0.1',
                        help='IP address of ADB server (Default: 127.0.0.1)')

    parser.add_argument('-adpservprt', '--adb_server_port', type=int, default=5037,
                        help='Port of ADB server (Default: 5037)')

    # log settings
    parser.add_argument('--no_file_logs', action='store_true', default=False,
                        help="Disable file logging (Default: file logging is enabled by default)")
    parser.add_argument('--log_path', default="logs/",
                        help="Defines directory to save log files to.")
    parser.add_argument('--log_level',
                        help=("Forces a certain log level. By default"
                              " it's set to INFO while being modified"
                              " by the -v command to show DEBUG logs."
                              " Custom log levels like DEBUG[1-5] can"
                              " be used too."))
    parser.add_argument("--log_file_rotation", default="50 MB",
                        help=("This parameter expects a human-readable value like"
                              " '18:00', 'sunday', 'weekly', 'monday at 12:00' or"
                              " a maximum file size like '100 MB' or '0.5 GB'."
                              " Set to '0' to disable completely. (Default: 50 MB)"))
    parser.add_argument("--log_file_level",
                        help="File logging level. See description for --log_level.")
    parser.add_argument("--log_file_retention", default="10",
                        help=("Amount of days to keep file logs. Set to 0 to"
                              " keep them forever (Default: 10)"))
    parser.add_argument('--log_filename', default='%Y%m%d_%H%M_<SN>.log',
                        help=("Defines the log filename to be saved."
                              " Allows date formatting, and replaces <SN>"
                              " with the instance's status name. Read the"
                              " python time module docs for details."
                              " Default: %%Y%%m%%d_%%H%%M_<SN>.log."))
    parser.add_argument('--no_log_colors', action="store_true", default=False,
                        help=("Disable colored logs."))

    parser.add_argument("-sn", "--status-name", default="mad",
                        help=("Enable status page database update using"
                              " STATUS_NAME as main worker name."))

    parser.add_argument('-ah', '--auto_hatch', action='store_true', default=False,
                        help='Activate auto hatch of level 5 eggs')

    parser.add_argument('-ahn', '--auto_hatch_number', type=int, default=0,
                        help='Auto hatch of level 5 Pokemon ID')

    parser.add_argument('-nec', '--no_event_checker', action="store_true",
                        help='Disable event checker task')

    verbose = parser.add_mutually_exclusive_group()
    verbose.add_argument('-v', action='count', default=0, dest='verbose',
                         help=("Show debug messages. Has no effect, if"
                               "--log_level has been set."))

    verbose.add_argument('--verbosity',
                         help='Show debug messages',
                         type=int, dest='verbose')
    parser.set_defaults(DEBUG=False)
    parser.add_argument('-ut', '--unit_tests', action='store_true', default=False,
                        help='Run unit tests then quit', dest='unit_tests')

    # MADAPKs
    parser.add_argument('-td', '--token_dispenser', default=default_tokenfile,
                        help='Token dispenser config (MAD)')
    parser.add_argument('-tdu', '--token_dispenser_user', default='',
                        help='Token dispenser config (User)')
    parser.add_argument('-gu', '--gmail_user', default='',
                        help='Google Mail User for interacting with the Google Play Store')
    parser.add_argument('-gp', '--gmail_passwd', default='',
                        help='Google Mail Password for interacting with the Google Play Store.  Must be an app'
                        ' password or 2fa will be triggered (this should be enabled on your account anyways')

    args = parser.parse_args()

    # Allow status name and date formatting in log filename.
    args.log_filename = strftime(args.log_filename)
    args.log_filename = args.log_filename.replace('<sn>', '<SN>')
    args.log_filename = args.log_filename.replace('<SN>', args.status_name)

    return args
