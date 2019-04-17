import os
import sys
from time import strftime

import configargparse


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
    if '-cf' not in sys.argv and '--config' not in sys.argv:
        defaultconfigfiles = [os.getenv('MAD_CONFIG', os.path.join(
            os.path.dirname(__file__), '../configs/config.ini'))]
    parser = configargparse.ArgParser(
        default_config_files=defaultconfigfiles,
        auto_env_var_prefix='THERAIDMAPPER_')
    parser.add_argument('-cf', '--config',
                        is_config_file=True, help='Set configuration file')

    # MySQL
    parser.add_argument('-dbm', '--db_method', required=False,
                        help='DB scheme to be used. Either "monocle" or "rm".')
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

    # Runtypes
    parser.add_argument('-os', '--only_scan', action='store_true', default=False,
                        help='Use this instance only for scanning.')
    parser.add_argument('-oo', '--only_ocr', action='store_true', default=False,
                        help='Use this instance only for OCR.')
    parser.add_argument('-om', '--ocr_multitask', action='store_true', default=False,
                        help='Running OCR in sub-processes (module multiprocessing) to speed up analysis of raids.')
    parser.add_argument('-otc', '--ocr_thread_count', type=int, default=2,
                        help='Amount of threads/processes to be used for screenshot-analysis.')
    parser.add_argument('-wm', '--with_madmin', action='store_true', default=False,
                        help='Start madmin as instance.')
    parser.add_argument('-or', '--only_routes', action='store_true', default=False,
                        help='Only calculate routes, then exit the program. No scanning.')
    parser.add_argument('-nocr', '--no_ocr', action='store_true', default=False,
                        help='Activate if you not using OCR for Quest or Raidscanning.')

    # folder
    parser.add_argument('-tmp', '--temp_path', default='temp',
                        help='Temp Folder for OCR Scanning. Default: temp')

    parser.add_argument('-pgasset', '--pogoasset', required=False,
                        help=('Path to Pogo Asset.'
                              'See https://github.com/ZeChrales/PogoAssets/'))

    parser.add_argument('-rscrpath', '--raidscreen_path', default='ocr/screenshots',  # TODO: check if user appended / or not and deal accordingly (rmeove it?)
                        help='Folder for processed Raidscreens. Default: ocr/screenshots')

    parser.add_argument('-unkpath', '--unknown_path', default='unknown',
                        help='Folder for unknows Gyms or Mons. Default: ocr/unknown')

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
                        help='URL endpoint/s for webhooks (seperated by commas) with [<type>] for restriction like [mon|weather|raid]http://example.org/foo/bar - urls have to start with http*')
    parser.add_argument('-pwh', '--pokemon_webhook', action='store_true', default=False,
                        help='Activate pokemon webhook support')
    parser.add_argument('-wwh', '--weather_webhook', action='store_true', default=False,
                        help='Activate weather webhook support')
    parser.add_argument('-qwh', '--quest_webhook', action='store_true', default=False,
                        help='Activate quest webhook support')
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

    parser.add_argument('-pfile', '--position_file', default='current',
                        help='Filename for bot\'s current position (Default: current)')

    parser.add_argument('-ugd', '--unknown_gym_distance', default='10',
                        help='Show matchable gyms for unknwon with this radius (in km!) (Default: 10)')

    # etc

    parser.add_argument('-rdt', '--raid_time', default='45', type=int,
                        help='Raid Battle time in minutes. (Default: 45)')
    parser.add_argument('-ump', '--use_media_projection', action='store_true', default=False,
                        help='Use Media Projection for image transfer (OCR) (Default: False)')

    # adb
    parser.add_argument('-adb', '--use_adb', action='store_true', default=False,
                        help='Use ADB for phonecontrol (Default: False)')
    parser.add_argument('-adbservip', '--adb_server_ip', default='127.0.0.1',
                        help='IP address of ADB server (Default: 127.0.0.1)')

    parser.add_argument('-adpservprt', '--adb_server_port', type=int, default=5037,
                        help='Port of ADB server (Default: 5037)')

    # log settings
    parser.add_argument('--no-file-logs',
                        help=('Disable logging to files. ' +
                              'Does not disable --access-logs.'),
                        action='store_true', default=False)
    parser.add_argument('--log-path',
                        help='Defines directory to save log files to.',
                        default='logs/')
    parser.add_argument('--log-filename',
                        help=('Defines the log filename to be saved.'
                              ' Allows date formatting, and replaces <SN>'
                              " with the instance's status name. Read the"
                              ' python time module docs for details.'
                              ' Default: %%Y%%m%%d_%%H%%M_<SN>.log.'),
                        default='%Y%m%d_%H%M_<SN>.log')
    parser.add_argument('-sn', '--status-name', default=str(os.getpid()),
                        help=('Enable status page database update using ' +
                              'STATUS_NAME as main worker name.'))
    parser.add_argument('-cla', '--cleanup-age', default=0, type=int,
                        help='Delete logs older than X minutes. Default: 0')

    parser.add_argument('-ah', '--auto_hatch', action='store_true', default=False,
                        help='Activate auto hatch of level 5 eggs')

    parser.add_argument('-ahn', '--auto_hatch_number', type=int, default=0,
                        help='Auto hatch of level 5 Pokemon ID')

    verbose = parser.add_mutually_exclusive_group()
    verbose.add_argument('-v',
                         help='Show debug messages',
                         action='count', default=0, dest='verbose')
    verbose.add_argument('--verbosity',
                         help='Show debug messages',
                         type=int, dest='verbose')
    parser.set_defaults(DEBUG=False)

    args = parser.parse_args()
    # Allow status name and date formatting in log filename.
    args.log_filename = strftime(args.log_filename)
    args.log_filename = args.log_filename.replace('<sn>', '<SN>')
    args.log_filename = args.log_filename.replace('<SN>', args.status_name)
    return args
