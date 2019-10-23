import base64
import re

from mapadroid.utils.logging import logger


def check_auth(authHeader, args, auths):
    valid = False
    if auths is None:
        return False
    try:
        auth_code = re.match(r'^Basic (\S+)$', authHeader)
        decoded = base64.b64decode(auth_code.group(1)).decode('utf-8')
        (username, password) = decoded.split(":", 1)
        if auths[username] != password:
            logger.warning("Auth attempt from {} failed", str(authHeader))
        else:
            valid = True
    except AttributeError as err:
        logger.warning("Auth without Basic auth, aborting.")
    except KeyError:
        logger.warning('Auth attempt from non-configured user {}', str(username))
    except TypeError as err:
        logger.warning('Unable to decode header {}', str(authHeader))
    except ValueError as err:
        logger.warning('Unable to determine auth parameters from {}', str(authHeader))
    return valid
