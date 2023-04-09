import base64
import re
from typing import Dict, Optional

from mapadroid.db.model import SettingsAuth


def check_auth(logger, auth_header: Optional[str], auths: Dict[str, SettingsAuth]):
    if auths is None:
        return True
    elif not auth_header:
        return False
    username: Optional[str] = None
    try:
        auth_code = re.match(r'^Basic (\S+)$', auth_header)
        decoded = base64.b64decode(auth_code.group(1)).decode('utf-8')
        (username, password) = decoded.split(":", 1)
        if auths[username].password != password:
            logger.warning("Auth attempt from {} failed", auth_header)
        else:
            return True
    except AttributeError:
        logger.warning("Auth without Basic auth, aborting.")
    except KeyError:
        logger.warning('Auth attempt from non-configured user {}', username)
    except TypeError:
        logger.warning('Unable to decode header {}', auth_header)
    except ValueError:
        logger.warning('Unable to determine auth parameters from {}', auth_header)
    except Exception as e:
        logger.error("Auth attempt failed: {}", e)
    return False
