# Run in mad root directory
# python3 -b scripts/doc_field_generator.py
import os
import sys

import mapadroid.madmin.api

sys.path.append(os.getcwd())

EXPECTED_TYPES = {
    str: 'String',
    int: 'Integer',
    float: 'Decimal',
    list: 'Comma-delimited list',
    bool: 'Boolean'
}


def print_api_doc(elem):
    if 'fields' in elem:
        print('## Fields')
        print('| Field Name | Type  | Required  | Description   |')
        print('| --         | --    | --        | --            |')
        print_section(elem['fields'])
    if 'settings' in elem:
        print('## Settings')
        print('| Field Name | Type  | Required  | Description   |')
        print('| --         | --    | --        | --            |')
        print_section(elem['settings'])


def print_section(sect):
    keys = sorted(sect.keys())
    for key in keys:
        val = sect[key]
        field = val['settings']
        args = []
        args.append(safe_convert(key))
        args.append(safe_convert(EXPECTED_TYPES[field['expected']]))
        args.append(field['require'])
        args.append(safe_convert(field['description']))
        print('|%s|%s|%s|%s|' % tuple(args))
    print('')


def safe_convert(thing):
    return thing.replace('|', '\|')


for module_name, elem in mapadroid.madmin.api.valid_modules.items():
    print('# %s' % (module_name))
    config = elem.configuration
    if 'fields' in config:
        print_api_doc(config)
    else:
        keys = sorted(config.keys())
        for mode_name in keys:
            print('# %s' % mode_name)
            print_api_doc(config[mode_name])
    print('\n\n')
