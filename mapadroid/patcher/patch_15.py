from ._patch_base import PatchBase
import json
import re


class Patch(PatchBase):
    name = 'Patch 15'

    def _execute(self):
        try:
            with open(self._application_args.mappings, 'rb') as fh:
                settings = json.load(fh)
            self.__convert_to_id(settings)
            with open(self._application_args.mappings, 'w') as outfile:
                json.dump(settings, outfile, indent=4, sort_keys=True)
        except IOError:
            pass

    def __convert_to_id(self, data):
        regex = re.compile(r'/api/.*/\d+')
        for key, val in data.items():
            if type(val) is dict:
                data[key] = self.__convert_to_id(val)
            elif type(val) is list:
                valid = []
                for elem in val:
                    if type(elem) is str:
                        valid.append(elem[elem.rfind('/') + 1:])
                    else:
                        valid.append(elem)
                data[key] = valid
            elif type(val) is str and regex.search(val):
                data[key] = val[val.rfind('/') + 1:]
        return data
