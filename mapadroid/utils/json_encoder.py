import json
from mapadroid.data_manager.modules.resource import Resource
from mapadroid.mad_apk.apk_enums import APK_Arch, APK_Type
from mapadroid.mad_apk.custom_types import MAD_Package, MAD_Packages, MAD_APKS


class MAD_Encoder(json.JSONEncoder):
    def apk_encode(self, o):
        if isinstance(o, MAD_APKS) or isinstance(o, MAD_Packages):
            updated = {}
            for key, val in o.items():
                updated[str(key.name)] = self.apk_encode(val)
            o = updated
        return o

    def encode(self, o, *args, **kw):
        for_json = o
        if isinstance(o, MAD_APKS) or isinstance(o, MAD_Packages):
            for_json = self.apk_encode(o)
        return super(MAD_Encoder, self).encode(for_json, *args, **kw)

    def default(self, obj):
        if isinstance(obj, MAD_Package):
            return obj.get_package(backend=False)
        elif isinstance(obj, APK_Arch):
            return obj.value
        elif isinstance(obj, APK_Type):
            return obj.value
        elif isinstance(obj, Resource):
            return obj.get_resource()
        elif isinstance(obj, MAD_APKS):
            return json.JSONEncoder.default(self, obj)
        return json.JSONEncoder.default(self, obj)
