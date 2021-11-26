# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: stats_handler/stats_handler.proto
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from google.protobuf import reflection as _reflection
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


from mapadroid.grpc.compiled.shared import Location_pb2 as shared_dot_Location__pb2
from mapadroid.grpc.compiled.shared import Ack_pb2 as shared_dot_Ack__pb2
from mapadroid.grpc.compiled.shared import PositionType_pb2 as shared_dot_PositionType__pb2
from mapadroid.grpc.compiled.shared import TransportType_pb2 as shared_dot_TransportType__pb2
from mapadroid.grpc.compiled.shared import MonSeenTypes_pb2 as shared_dot_MonSeenTypes__pb2
from mapadroid.grpc.compiled.shared import Worker_pb2 as shared_dot_Worker__pb2


DESCRIPTOR = _descriptor.FileDescriptor(
  name='stats_handler/stats_handler.proto',
  package='mapadroid.stats_handler',
  syntax='proto3',
  serialized_options=None,
  create_key=_descriptor._internal_create_key,
  serialized_pb=b'\n!stats_handler/stats_handler.proto\x12\x17mapadroid.stats_handler\x1a\x15shared/Location.proto\x1a\x10shared/Ack.proto\x1a\x19shared/PositionType.proto\x1a\x1ashared/TransportType.proto\x1a\x19shared/MonSeenTypes.proto\x1a\x13shared/Worker.proto\"\xd9\x03\n\x05Stats\x12-\n\x06worker\x18\x01 \x01(\x0b\x32\x18.mapadroid.shared.WorkerH\x01\x88\x01\x01\x12\x16\n\ttimestamp\x18\x02 \x01(\x04H\x02\x88\x01\x01\x12:\n\twild_mons\x18\x03 \x01(\x0b\x32%.mapadroid.stats_handler.StatsWildMonH\x00\x12\x35\n\x06mon_iv\x18\x04 \x01(\x0b\x32#.mapadroid.stats_handler.StatsMonIvH\x00\x12\x34\n\x05quest\x18\x05 \x01(\x0b\x32#.mapadroid.stats_handler.StatsQuestH\x00\x12\x32\n\x04raid\x18\x06 \x01(\x0b\x32\".mapadroid.stats_handler.StatsRaidH\x00\x12\x43\n\rlocation_data\x18\x07 \x01(\x0b\x32*.mapadroid.stats_handler.StatsLocationDataH\x00\x12;\n\tseen_type\x18\x08 \x01(\x0b\x32&.mapadroid.stats_handler.StatsSeenTypeH\x00\x42\x11\n\x0f\x64\x61ta_to_collectB\t\n\x07_workerB\x0c\n\n_timestamp\"%\n\x0cStatsWildMon\x12\x15\n\rencounter_ids\x18\x01 \x03(\x04\"4\n\nStatsMonIv\x12\x14\n\x0c\x65ncounter_id\x18\x01 \x01(\x04\x12\x10\n\x08is_shiny\x18\x02 \x01(\x08\"\x0c\n\nStatsQuest\"\x1b\n\tStatsRaid\x12\x0e\n\x06\x61mount\x18\x01 \x01(\r\"\x81\x02\n\x11StatsLocationData\x12,\n\x08location\x18\x01 \x01(\x0b\x32\x1a.mapadroid.shared.Location\x12\x0f\n\x07success\x18\x02 \x01(\x08\x12\x15\n\rfix_timestamp\x18\x03 \x01(\x04\x12\x16\n\x0e\x64\x61ta_timestamp\x18\x04 \x01(\x04\x12\x35\n\rposition_type\x18\x05 \x01(\x0e\x32\x1e.mapadroid.shared.PositionType\x12\x0e\n\x06walker\x18\x06 \x01(\t\x12\x37\n\x0etransport_type\x18\x07 \x01(\x0e\x32\x1f.mapadroid.shared.TransportType\"a\n\rStatsSeenType\x12\x15\n\rencounter_ids\x18\x01 \x03(\x04\x12\x39\n\x11type_of_detection\x18\x02 \x01(\x0e\x32\x1e.mapadroid.shared.MonSeenTypes2U\n\x0cStatsHandler\x12\x45\n\x0cStatsCollect\x12\x1e.mapadroid.stats_handler.Stats\x1a\x15.mapadroid.shared.Ackb\x06proto3'
  ,
  dependencies=[shared_dot_Location__pb2.DESCRIPTOR,shared_dot_Ack__pb2.DESCRIPTOR,shared_dot_PositionType__pb2.DESCRIPTOR,shared_dot_TransportType__pb2.DESCRIPTOR,shared_dot_MonSeenTypes__pb2.DESCRIPTOR,shared_dot_Worker__pb2.DESCRIPTOR,])




_STATS = _descriptor.Descriptor(
  name='Stats',
  full_name='mapadroid.stats_handler.Stats',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  create_key=_descriptor._internal_create_key,
  fields=[
    _descriptor.FieldDescriptor(
      name='worker', full_name='mapadroid.stats_handler.Stats.worker', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
    _descriptor.FieldDescriptor(
      name='timestamp', full_name='mapadroid.stats_handler.Stats.timestamp', index=1,
      number=2, type=4, cpp_type=4, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
    _descriptor.FieldDescriptor(
      name='wild_mons', full_name='mapadroid.stats_handler.Stats.wild_mons', index=2,
      number=3, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
    _descriptor.FieldDescriptor(
      name='mon_iv', full_name='mapadroid.stats_handler.Stats.mon_iv', index=3,
      number=4, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
    _descriptor.FieldDescriptor(
      name='quest', full_name='mapadroid.stats_handler.Stats.quest', index=4,
      number=5, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
    _descriptor.FieldDescriptor(
      name='raid', full_name='mapadroid.stats_handler.Stats.raid', index=5,
      number=6, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
    _descriptor.FieldDescriptor(
      name='location_data', full_name='mapadroid.stats_handler.Stats.location_data', index=6,
      number=7, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
    _descriptor.FieldDescriptor(
      name='seen_type', full_name='mapadroid.stats_handler.Stats.seen_type', index=7,
      number=8, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
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
    _descriptor.OneofDescriptor(
      name='data_to_collect', full_name='mapadroid.stats_handler.Stats.data_to_collect',
      index=0, containing_type=None,
      create_key=_descriptor._internal_create_key,
    fields=[]),
    _descriptor.OneofDescriptor(
      name='_worker', full_name='mapadroid.stats_handler.Stats._worker',
      index=1, containing_type=None,
      create_key=_descriptor._internal_create_key,
    fields=[]),
    _descriptor.OneofDescriptor(
      name='_timestamp', full_name='mapadroid.stats_handler.Stats._timestamp',
      index=2, containing_type=None,
      create_key=_descriptor._internal_create_key,
    fields=[]),
  ],
  serialized_start=207,
  serialized_end=680,
)


_STATSWILDMON = _descriptor.Descriptor(
  name='StatsWildMon',
  full_name='mapadroid.stats_handler.StatsWildMon',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  create_key=_descriptor._internal_create_key,
  fields=[
    _descriptor.FieldDescriptor(
      name='encounter_ids', full_name='mapadroid.stats_handler.StatsWildMon.encounter_ids', index=0,
      number=1, type=4, cpp_type=4, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
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
  serialized_start=682,
  serialized_end=719,
)


_STATSMONIV = _descriptor.Descriptor(
  name='StatsMonIv',
  full_name='mapadroid.stats_handler.StatsMonIv',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  create_key=_descriptor._internal_create_key,
  fields=[
    _descriptor.FieldDescriptor(
      name='encounter_id', full_name='mapadroid.stats_handler.StatsMonIv.encounter_id', index=0,
      number=1, type=4, cpp_type=4, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
    _descriptor.FieldDescriptor(
      name='is_shiny', full_name='mapadroid.stats_handler.StatsMonIv.is_shiny', index=1,
      number=2, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
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
  serialized_start=721,
  serialized_end=773,
)


_STATSQUEST = _descriptor.Descriptor(
  name='StatsQuest',
  full_name='mapadroid.stats_handler.StatsQuest',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  create_key=_descriptor._internal_create_key,
  fields=[
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
  serialized_start=775,
  serialized_end=787,
)


_STATSRAID = _descriptor.Descriptor(
  name='StatsRaid',
  full_name='mapadroid.stats_handler.StatsRaid',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  create_key=_descriptor._internal_create_key,
  fields=[
    _descriptor.FieldDescriptor(
      name='amount', full_name='mapadroid.stats_handler.StatsRaid.amount', index=0,
      number=1, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
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
  serialized_start=789,
  serialized_end=816,
)


_STATSLOCATIONDATA = _descriptor.Descriptor(
  name='StatsLocationData',
  full_name='mapadroid.stats_handler.StatsLocationData',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  create_key=_descriptor._internal_create_key,
  fields=[
    _descriptor.FieldDescriptor(
      name='location', full_name='mapadroid.stats_handler.StatsLocationData.location', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
    _descriptor.FieldDescriptor(
      name='success', full_name='mapadroid.stats_handler.StatsLocationData.success', index=1,
      number=2, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
    _descriptor.FieldDescriptor(
      name='fix_timestamp', full_name='mapadroid.stats_handler.StatsLocationData.fix_timestamp', index=2,
      number=3, type=4, cpp_type=4, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
    _descriptor.FieldDescriptor(
      name='data_timestamp', full_name='mapadroid.stats_handler.StatsLocationData.data_timestamp', index=3,
      number=4, type=4, cpp_type=4, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
    _descriptor.FieldDescriptor(
      name='position_type', full_name='mapadroid.stats_handler.StatsLocationData.position_type', index=4,
      number=5, type=14, cpp_type=8, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
    _descriptor.FieldDescriptor(
      name='walker', full_name='mapadroid.stats_handler.StatsLocationData.walker', index=5,
      number=6, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=b"".decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
    _descriptor.FieldDescriptor(
      name='transport_type', full_name='mapadroid.stats_handler.StatsLocationData.transport_type', index=6,
      number=7, type=14, cpp_type=8, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
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
  serialized_start=819,
  serialized_end=1076,
)


_STATSSEENTYPE = _descriptor.Descriptor(
  name='StatsSeenType',
  full_name='mapadroid.stats_handler.StatsSeenType',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  create_key=_descriptor._internal_create_key,
  fields=[
    _descriptor.FieldDescriptor(
      name='encounter_ids', full_name='mapadroid.stats_handler.StatsSeenType.encounter_ids', index=0,
      number=1, type=4, cpp_type=4, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
    _descriptor.FieldDescriptor(
      name='type_of_detection', full_name='mapadroid.stats_handler.StatsSeenType.type_of_detection', index=1,
      number=2, type=14, cpp_type=8, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
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
  serialized_start=1078,
  serialized_end=1175,
)

_STATS.fields_by_name['worker'].message_type = shared_dot_Worker__pb2._WORKER
_STATS.fields_by_name['wild_mons'].message_type = _STATSWILDMON
_STATS.fields_by_name['mon_iv'].message_type = _STATSMONIV
_STATS.fields_by_name['quest'].message_type = _STATSQUEST
_STATS.fields_by_name['raid'].message_type = _STATSRAID
_STATS.fields_by_name['location_data'].message_type = _STATSLOCATIONDATA
_STATS.fields_by_name['seen_type'].message_type = _STATSSEENTYPE
_STATS.oneofs_by_name['data_to_collect'].fields.append(
  _STATS.fields_by_name['wild_mons'])
_STATS.fields_by_name['wild_mons'].containing_oneof = _STATS.oneofs_by_name['data_to_collect']
_STATS.oneofs_by_name['data_to_collect'].fields.append(
  _STATS.fields_by_name['mon_iv'])
_STATS.fields_by_name['mon_iv'].containing_oneof = _STATS.oneofs_by_name['data_to_collect']
_STATS.oneofs_by_name['data_to_collect'].fields.append(
  _STATS.fields_by_name['quest'])
_STATS.fields_by_name['quest'].containing_oneof = _STATS.oneofs_by_name['data_to_collect']
_STATS.oneofs_by_name['data_to_collect'].fields.append(
  _STATS.fields_by_name['raid'])
_STATS.fields_by_name['raid'].containing_oneof = _STATS.oneofs_by_name['data_to_collect']
_STATS.oneofs_by_name['data_to_collect'].fields.append(
  _STATS.fields_by_name['location_data'])
_STATS.fields_by_name['location_data'].containing_oneof = _STATS.oneofs_by_name['data_to_collect']
_STATS.oneofs_by_name['data_to_collect'].fields.append(
  _STATS.fields_by_name['seen_type'])
_STATS.fields_by_name['seen_type'].containing_oneof = _STATS.oneofs_by_name['data_to_collect']
_STATS.oneofs_by_name['_worker'].fields.append(
  _STATS.fields_by_name['worker'])
_STATS.fields_by_name['worker'].containing_oneof = _STATS.oneofs_by_name['_worker']
_STATS.oneofs_by_name['_timestamp'].fields.append(
  _STATS.fields_by_name['timestamp'])
_STATS.fields_by_name['timestamp'].containing_oneof = _STATS.oneofs_by_name['_timestamp']
_STATSLOCATIONDATA.fields_by_name['location'].message_type = shared_dot_Location__pb2._LOCATION
_STATSLOCATIONDATA.fields_by_name['position_type'].enum_type = shared_dot_PositionType__pb2._POSITIONTYPE
_STATSLOCATIONDATA.fields_by_name['transport_type'].enum_type = shared_dot_TransportType__pb2._TRANSPORTTYPE
_STATSSEENTYPE.fields_by_name['type_of_detection'].enum_type = shared_dot_MonSeenTypes__pb2._MONSEENTYPES
DESCRIPTOR.message_types_by_name['Stats'] = _STATS
DESCRIPTOR.message_types_by_name['StatsWildMon'] = _STATSWILDMON
DESCRIPTOR.message_types_by_name['StatsMonIv'] = _STATSMONIV
DESCRIPTOR.message_types_by_name['StatsQuest'] = _STATSQUEST
DESCRIPTOR.message_types_by_name['StatsRaid'] = _STATSRAID
DESCRIPTOR.message_types_by_name['StatsLocationData'] = _STATSLOCATIONDATA
DESCRIPTOR.message_types_by_name['StatsSeenType'] = _STATSSEENTYPE
_sym_db.RegisterFileDescriptor(DESCRIPTOR)

Stats = _reflection.GeneratedProtocolMessageType('Stats', (_message.Message,), {
  'DESCRIPTOR' : _STATS,
  '__module__' : 'stats_handler.stats_handler_pb2'
  # @@protoc_insertion_point(class_scope:mapadroid.stats_handler.Stats)
  })
_sym_db.RegisterMessage(Stats)

StatsWildMon = _reflection.GeneratedProtocolMessageType('StatsWildMon', (_message.Message,), {
  'DESCRIPTOR' : _STATSWILDMON,
  '__module__' : 'stats_handler.stats_handler_pb2'
  # @@protoc_insertion_point(class_scope:mapadroid.stats_handler.StatsWildMon)
  })
_sym_db.RegisterMessage(StatsWildMon)

StatsMonIv = _reflection.GeneratedProtocolMessageType('StatsMonIv', (_message.Message,), {
  'DESCRIPTOR' : _STATSMONIV,
  '__module__' : 'stats_handler.stats_handler_pb2'
  # @@protoc_insertion_point(class_scope:mapadroid.stats_handler.StatsMonIv)
  })
_sym_db.RegisterMessage(StatsMonIv)

StatsQuest = _reflection.GeneratedProtocolMessageType('StatsQuest', (_message.Message,), {
  'DESCRIPTOR' : _STATSQUEST,
  '__module__' : 'stats_handler.stats_handler_pb2'
  # @@protoc_insertion_point(class_scope:mapadroid.stats_handler.StatsQuest)
  })
_sym_db.RegisterMessage(StatsQuest)

StatsRaid = _reflection.GeneratedProtocolMessageType('StatsRaid', (_message.Message,), {
  'DESCRIPTOR' : _STATSRAID,
  '__module__' : 'stats_handler.stats_handler_pb2'
  # @@protoc_insertion_point(class_scope:mapadroid.stats_handler.StatsRaid)
  })
_sym_db.RegisterMessage(StatsRaid)

StatsLocationData = _reflection.GeneratedProtocolMessageType('StatsLocationData', (_message.Message,), {
  'DESCRIPTOR' : _STATSLOCATIONDATA,
  '__module__' : 'stats_handler.stats_handler_pb2'
  # @@protoc_insertion_point(class_scope:mapadroid.stats_handler.StatsLocationData)
  })
_sym_db.RegisterMessage(StatsLocationData)

StatsSeenType = _reflection.GeneratedProtocolMessageType('StatsSeenType', (_message.Message,), {
  'DESCRIPTOR' : _STATSSEENTYPE,
  '__module__' : 'stats_handler.stats_handler_pb2'
  # @@protoc_insertion_point(class_scope:mapadroid.stats_handler.StatsSeenType)
  })
_sym_db.RegisterMessage(StatsSeenType)



_STATSHANDLER = _descriptor.ServiceDescriptor(
  name='StatsHandler',
  full_name='mapadroid.stats_handler.StatsHandler',
  file=DESCRIPTOR,
  index=0,
  serialized_options=None,
  create_key=_descriptor._internal_create_key,
  serialized_start=1177,
  serialized_end=1262,
  methods=[
  _descriptor.MethodDescriptor(
    name='StatsCollect',
    full_name='mapadroid.stats_handler.StatsHandler.StatsCollect',
    index=0,
    containing_service=None,
    input_type=_STATS,
    output_type=shared_dot_Ack__pb2._ACK,
    serialized_options=None,
    create_key=_descriptor._internal_create_key,
  ),
])
_sym_db.RegisterServiceDescriptor(_STATSHANDLER)

DESCRIPTOR.services_by_name['StatsHandler'] = _STATSHANDLER

# @@protoc_insertion_point(module_scope)