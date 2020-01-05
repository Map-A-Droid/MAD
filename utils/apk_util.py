from utils import global_variables

def get_mad_apks(db):
    apks = {
        'pogo': {
            'armeabi-v7a': {
                'version': None,
                'file_id': None,
            },
            'arm64-v8a': {
                'version': None,
                'file_id': None,
            },
        },
        'rgc': {
            'noarch': {
                'version': None,
                'file_id': None,
            },
        },
        'pogodroid': {
            'noarch': {
                'version': None,
                'file_id': None,
            },
        }
    }
    sql = "SELECT * FROM `mad_apks`"
    mad_apks = db.autofetch_all(sql)
    for apk in mad_apks:
        apk_type = None
        apk_arch = None
        if apk['usage'] == global_variables.MAD_APK_USAGE_POGO:
            apk_type = 'pogo'
            if apk['arch'] == global_variables.MAD_APK_ARCH_ARMEABI_V7A:
                apk_arch = 'armeabi-v7a'
            else:
                apk_arch = 'arm64-v8a'
        elif apk['usage'] == global_variables.MAD_APK_USAGE_RGC:
            apk_type = 'rgc'
            apk_arch = 'noarch'
        elif apk['usage'] == global_variables.MAD_APK_USAGE_PD:
            apk_type = 'pogodroid'
            apk_arch = 'noarch'
        apks[apk_type][apk_arch] = {
            'version': apk['version'],
            'file_id': apk['id']
        }
    return apks