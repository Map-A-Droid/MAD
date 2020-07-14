import json
from mapadroid.data_manager.modules.resource import Resource
from mapadroid.mad_apk.apk_enums import APK_Arch, APK_Type
from mapadroid.mad_apk.custom_types import MAD_Package, MAD_Packages, MAD_APKS


class MAD_Encoder(json.JSONEncoder):
    def apk_encode(self, object_to_encode):
        if isinstance(object_to_encode, MAD_APKS) or isinstance(object_to_encode, MAD_Packages):
            updated = {}
            for obj_key, key_value in object_to_encode.items():
                updated[str(obj_key.name)] = self.apk_encode(key_value)
            object_to_encode = updated
        return object_to_encode

    def encode(self, object_to_encode, *args, **kw):
        for_json = object_to_encode
        if isinstance(object_to_encode, MAD_APKS) or isinstance(object_to_encode, MAD_Packages):
            for_json = self.apk_encode(object_to_encode)
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
