# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: pogoprotos/settings/sfida_settings.proto

from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from google.protobuf import reflection as _reflection
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()




DESCRIPTOR = _descriptor.FileDescriptor(
  name='pogoprotos/settings/sfida_settings.proto',
  package='pogoprotos.settings',
  syntax='proto3',
  serialized_options=None,
  serialized_pb=b'\n(pogoprotos/settings/sfida_settings.proto\x12\x13pogoprotos.settings\".\n\rSfidaSettings\x12\x1d\n\x15low_battery_threshold\x18\x01 \x01(\x02\x62\x06proto3'
)




_SFIDASETTINGS = _descriptor.Descriptor(
  name='SfidaSettings',
  full_name='pogoprotos.settings.SfidaSettings',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='low_battery_threshold', full_name='pogoprotos.settings.SfidaSettings.low_battery_threshold', index=0,
      number=1, type=2, cpp_type=6, label=1,
      has_default_value=False, default_value=float(0),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  serialized_options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=65,
  serialized_end=111,
)

DESCRIPTOR.message_types_by_name['SfidaSettings'] = _SFIDASETTINGS
_sym_db.RegisterFileDescriptor(DESCRIPTOR)

SfidaSettings = _reflection.GeneratedProtocolMessageType('SfidaSettings', (_message.Message,), {
  'DESCRIPTOR' : _SFIDASETTINGS,
  '__module__' : 'pogoprotos.settings.sfida_settings_pb2'
  # @@protoc_insertion_point(class_scope:pogoprotos.settings.SfidaSettings)
  })
_sym_db.RegisterMessage(SfidaSettings)


# @@protoc_insertion_point(module_scope)