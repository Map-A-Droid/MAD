from utils import global_variables
from utils.logging import logger

def chunk_generator(dbc, filestore_id):
    sql = "SELECT `chunk_id` FROM `filestore_chunks` WHERE `filestore_id` = %s"
    data_sql = "SELECT `data` FROM `filestore_chunks` WHERE `chunk_id` = %s"
    chunk_ids = dbc.autofetch_column(sql, args=(filestore_id,))
    for chunk_id in chunk_ids:
        yield dbc.autofetch_value(data_sql, args=(chunk_id))

def get_mad_apks(db, front_end=False) -> dict:
    keys = {
       'pogo': global_variables.MAD_APK_USAGE_POGO,
       'rgc':  global_variables.MAD_APK_USAGE_RGC,
       'pogodroid': global_variables.MAD_APK_USAGE_PD
    }
    if front_end:
        keys = {
           'pogo': 'pogo',
           'rgc':  'rgc',
           'pogodroid': 'pogodroid'
        }
    apks = {
        keys['pogo']: {
            'armeabi-v7a': {
                'version': None,
                'file_id': None,
                'filename': None,
            },
            'arm64-v8a': {
                'version': None,
                'file_id': None,
                'filename': None,
            },
        },
        keys['rgc']: {
            'noarch': {
                'version': None,
                'file_id': None,
                'filename': None,
            },
        },
        keys['pogodroid']: {
            'noarch': {
                'version': None,
                'file_id': None,
                'filename': None,
            },
        }
    }
    sql = "SELECT * FROM `mad_apks`"
    file_sql = "SELECT `filename`, `size`, `mimetype` FROM `filestore_meta` WHERE `filestore_id` = %s"
    mad_apks = db.autofetch_all(sql)
    for apk in mad_apks:
        apk_type = None
        apk_arch = None
        file_data = db.autofetch_row(file_sql, args=(apk['filestore_id']))
        if apk['usage'] == global_variables.MAD_APK_USAGE_POGO:
            apk_name = 'pogo'
            if apk['arch'] == global_variables.MAD_APK_ARCH_ARMEABI_V7A:
                apk_arch = 'armeabi-v7a'
            else:
                apk_arch = 'arm64-v8a'
        elif apk['usage'] == global_variables.MAD_APK_USAGE_RGC:
            apk_name = 'rgc'
            apk_arch = 'noarch'
        elif apk['usage'] == global_variables.MAD_APK_USAGE_PD:
            apk_name = 'pogodroid'
            apk_arch = 'noarch'
        if not front_end:
            apk_name = apk['usage']
        file_data['version'] = apk['version']
        file_data['file_id'] = apk['filestore_id']
        apks[apk_name][apk_arch] = file_data
    return apks

def get_mad_apk(db, apk_type: str, architecture: str ='noarch') -> dict:
    apks = get_mad_apks(db)
    try:
        return apks[global_variables.MAD_APK_USAGE[apk_type]][architecture]
    except KeyError:
        if architecture != 'noarch':
            return get_mad_apk(db, apk_type)
        else:
            return False

def get_mad_apk_ver(db, apk_type: str, apk_arch: str ='noarch') -> str:
    apks = get_mad_apks(db)
    try:
        return get_mad_apk(db, apk_type, apk_arch=apk_arch)['version']
    except KeyError:
        return False

def has_newer_ver(installed: str, mad_ver: str) -> bool:
    mad_can_update = False
    if mad_ver == installed:
        return None
    split_mad = mad_ver.split('.')
    split_installed = installed.split('.')
    solution = False
    try:
        for ind, val in enumerate(split_mad):
            if int(val) < int(split_installed[ind]):
                solution = True
                break
    except KeyError:
        pass
    if not solution:
        mad_can_update = True
    return mad_can_update