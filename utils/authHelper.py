import base64
import logging

log = logging.getLogger(__name__)


def check_auth(authHeader, args, auths):
    if "Basic" not in authHeader:
        log.warning("Auth without Basic auth, aborting.")
        return False
    try:
        base64raw = authHeader.replace("Basic", "").replace(" ", "")
        decoded = str(base64.b64decode(base64raw))
    except TypeError:
        return False
    decodedSplit = decoded.split(":")
    # decoded.split(":")
    if args is not None and auths is not None:
        # check if user is present in ws_auth, if so also check pw
        # god awful dirty replace... no idea why the b' is in there...
        username = str(decodedSplit[0]).replace("b'", "")
        passwordInConf = auths.get(username, None)
        if passwordInConf is None or passwordInConf is not None and passwordInConf != decodedSplit[1].replace("'", ""):
            log.warning("Auth attempt from %s failed" % str(authHeader))
            return False
    return True
