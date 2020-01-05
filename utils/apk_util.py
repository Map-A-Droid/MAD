from utils import global_variables

def get_mad_apks(db):
    apks = {
        'pogo': {
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
        'rgc': {
            'noarch': {
                'version': None,
                'file_id': None,
                'filename': None,
            },
        },
        'pogodroid': {
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
        file_data['version'] = apk['version']
        file_data['file_id'] = apk['filestore_id']
        apks[apk_type][apk_arch] = file_data
    return apks