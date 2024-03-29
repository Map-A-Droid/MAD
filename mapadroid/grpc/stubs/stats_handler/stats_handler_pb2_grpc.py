# Generated by the gRPC Python protocol compiler plugin. DO NOT EDIT!
"""Client and server classes corresponding to protobuf-defined services."""
import grpc

from mapadroid.grpc.compiled.shared import Ack_pb2 as shared_dot_Ack__pb2
from mapadroid.grpc.compiled.stats_handler import stats_handler_pb2 as stats__handler_dot_stats__handler__pb2


class StatsHandlerStub(object):
    """Missing associated documentation comment in .proto file."""

    def __init__(self, channel):
        """Constructor.

        Args:
            channel: A grpc.Channel.
        """
        self.StatsCollect = channel.unary_unary(
                '/mapadroid.stats_handler.StatsHandler/StatsCollect',
                request_serializer=stats__handler_dot_stats__handler__pb2.Stats.SerializeToString,
                response_deserializer=shared_dot_Ack__pb2.Ack.FromString,
                )


class StatsHandlerServicer(object):
    """Missing associated documentation comment in .proto file."""

    def StatsCollect(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')


def add_StatsHandlerServicer_to_server(servicer, server):
    rpc_method_handlers = {
            'StatsCollect': grpc.unary_unary_rpc_method_handler(
                    servicer.StatsCollect,
                    request_deserializer=stats__handler_dot_stats__handler__pb2.Stats.FromString,
                    response_serializer=shared_dot_Ack__pb2.Ack.SerializeToString,
            ),
    }
    generic_handler = grpc.method_handlers_generic_handler(
            'mapadroid.stats_handler.StatsHandler', rpc_method_handlers)
    server.add_generic_rpc_handlers((generic_handler,))


 # This class is part of an EXPERIMENTAL API.
class StatsHandler(object):
    """Missing associated documentation comment in .proto file."""

    @staticmethod
    def StatsCollect(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/mapadroid.stats_handler.StatsHandler/StatsCollect',
            stats__handler_dot_stats__handler__pb2.Stats.SerializeToString,
            shared_dot_Ack__pb2.Ack.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)
