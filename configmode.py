import os
import sys
from threading import Thread

from utils.walkerArgs import parseArgs

args = parseArgs()
os.environ['LANGUAGE'] = args.language


def generate_mappingjson():
    import json
    newfile = {}
    newfile['areas'] = []
    newfile['auth'] = []
    newfile['devices'] = []
    with open('configs/mappings.json', 'w') as outfile:
        json.dump(newfile, outfile, indent=4, sort_keys=True)


def start_madmin():
    from madmin.madmin import app
    app.run(host=args.madmin_ip, port=int(args.madmin_port),
            threaded=True, use_reloader=False)


if __name__ == "__main__":
    filename = os.path.join('configs', 'config.ini')
    if not os.path.exists(filename):
        print('Config.ini not found - check configs folder and copy .example')
        sys.exit(1)

    filename = os.path.join('configs', 'mappings.json')
    if not os.path.exists(filename):
        generate_mappingjson()

    print('Starting MADmin with Port {} - open browser  and click "Mapping Editor"'.format(int(args.madmin_port)))
    t_flask = Thread(name='madmin', target=start_madmin)
    t_flask.daemon = False
    t_flask.start()
