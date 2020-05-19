import json
from mapadroid.data_manager.modules.resource import Resource
from mapadroid.mad_apk.apk_enums import APK_Arch, APK_Type
from mapadroid.mad_apk.custom_types import MAD_Package

class MAD_Encoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, MAD_Package):
            return obj.get_package(backend=False)
        elif isinstance(obj, APK_Arch):
            return obj.value
        elif isinstance(obj, APK_Type):
            return obj.value
        elif isinstance(obj, Resource):
            return obj.get_resource()
        return json.JSONEncoder.default(self, obj)