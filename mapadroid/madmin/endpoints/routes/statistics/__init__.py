from aiohttp import web

from mapadroid.madmin.endpoints.routes.statistics.ConvertSpawnEndpoint import ConvertSpawnEndpoint
from mapadroid.madmin.endpoints.routes.statistics.ConvertSpawnsEndpoint import ConvertSpawnsEndpoint
from mapadroid.madmin.endpoints.routes.statistics.DeleteSpawnEndpoint import DeleteSpawnEndpoint
from mapadroid.madmin.endpoints.routes.statistics.DeleteSpawnsEndpoint import DeleteSpawnsEndpoint
from mapadroid.madmin.endpoints.routes.statistics.DeleteStatusEntryEndpoint import DeleteStatusEntryEndpoint
from mapadroid.madmin.endpoints.routes.statistics.DeleteUnfencedSpawnsEndpoint import DeleteUnfencedSpawnsEndpoint
from mapadroid.madmin.endpoints.routes.statistics.GameStatsMonEndpoint import GameStatsMonEndpoint
from mapadroid.madmin.endpoints.routes.statistics.GameStatsShinyEndpoint import GameStatsShinyEndpoint
from mapadroid.madmin.endpoints.routes.statistics.GetGameStatsEndpoint import GetGameStatsEndpoint
from mapadroid.madmin.endpoints.routes.statistics.GetNonivEncountersCountEndpoint import GetNonivEncountersCountEndpoint
from mapadroid.madmin.endpoints.routes.statistics.GetSpawnDetailsEndpoint import GetSpawnDetailsEndpoint
from mapadroid.madmin.endpoints.routes.statistics.GetSpawnpointStatsEndpoint import GetSpawnpointStatsEndpoint
from mapadroid.madmin.endpoints.routes.statistics.GetSpawnpointStatsSummaryEndpoint import \
    GetSpawnpointStatsSummaryEndpoint
from mapadroid.madmin.endpoints.routes.statistics.GetStatusEndpoint import GetStatusEndpoint
from mapadroid.madmin.endpoints.routes.statistics.GetStopQuestStatsEndpoint import GetStopQuestStatsEndpoint
from mapadroid.madmin.endpoints.routes.statistics.ResetStatusEntryEndpoint import ResetStatusEntryEndpoint
from mapadroid.madmin.endpoints.routes.statistics.ShinyStatsEndpoint import ShinyStatsEndpoint
from mapadroid.madmin.endpoints.routes.statistics.SpawnDetailsEndpoint import SpawnDetailsEndpoint
from mapadroid.madmin.endpoints.routes.statistics.StatisticsDetectionWorkerDataEndpoint import \
    StatisticsDetectionWorkerDataEndpoint
from mapadroid.madmin.endpoints.routes.statistics.StatisticsDetectionWorkerEndpoint import \
    StatisticsDetectionWorkerEndpoint
from mapadroid.madmin.endpoints.routes.statistics.StatisticsEndpoint import StatisticsEndpoint
from mapadroid.madmin.endpoints.routes.statistics.StatisticsMonEndpoint import StatisticsMonEndpoint
from mapadroid.madmin.endpoints.routes.statistics.StatisticsShinyEndpoint import StatisticsShinyEndpoint
from mapadroid.madmin.endpoints.routes.statistics.StatisticsSpawnsEndpoint import StatisticsSpawnsEndpoint
from mapadroid.madmin.endpoints.routes.statistics.StatisticsStopQuestEndpoint import StatisticsStopQuestEndpoint
from mapadroid.madmin.endpoints.routes.statistics.StatusEndpoint import StatusEndpoint


def register_routes_statistics_endpoints(app: web.Application):
    app.router.add_view('/statistics', StatisticsEndpoint, name='statistics')
    app.router.add_view('/statistics_mon', StatisticsMonEndpoint, name='statistics_mon')
    app.router.add_view('/statistics_shiny', StatisticsShinyEndpoint, name='statistics_shiny')
    app.router.add_view('/get_game_stats_shiny', GameStatsShinyEndpoint, name='game_stats_shiny_v2')
    app.router.add_view('/get_game_stats', GetGameStatsEndpoint, name='game_stats')
    app.router.add_view('/get_game_stats_mon', GameStatsMonEndpoint, name='game_stats_mon')
    app.router.add_view('/statistics_detection_worker_data', StatisticsDetectionWorkerDataEndpoint,
                        name='statistics_detection_worker_data')
    app.router.add_view('/statistics_detection_worker', StatisticsDetectionWorkerEndpoint,
                        name='statistics_detection_worker')
    app.router.add_view('/status', StatusEndpoint, name='status')
    app.router.add_view('/get_status', GetStatusEndpoint, name='get_status')
    app.router.add_view('/get_spawnpoints_stats', GetSpawnpointStatsEndpoint, name='get_spawnpoints_stats')
    app.router.add_view('/get_spawnpoints_stats_summary', GetSpawnpointStatsSummaryEndpoint,
                        name='get_spawnpoints_stats_summary')
    app.router.add_view('/statistics_spawns', StatisticsSpawnsEndpoint, name='statistics_spawns')
    app.router.add_view('/shiny_stats', ShinyStatsEndpoint, name='shiny_stats')
    app.router.add_view('/delete_spawns', DeleteSpawnsEndpoint, name='delete_spawns')
    app.router.add_view('/convert_spawns', ConvertSpawnsEndpoint, name='convert_spawns')
    app.router.add_view('/spawn_details', SpawnDetailsEndpoint, name='spawn_details')
    app.router.add_view('/get_spawn_details', GetSpawnDetailsEndpoint, name='get_spawn_details')
    app.router.add_view('/delete_spawn', DeleteSpawnEndpoint, name='delete_spawn')
    app.router.add_view('/convert_spawn', ConvertSpawnEndpoint, name='convert_spawn')
    app.router.add_view('/delete_unfenced_spawns', DeleteUnfencedSpawnsEndpoint, name='delete_unfenced_spawns')
    app.router.add_view('/delete_status_entry', DeleteStatusEntryEndpoint, name='delete_status_entry')
    app.router.add_view('/reset_status_entry', ResetStatusEntryEndpoint, name='reset_status_entry')
    app.router.add_view('/get_stop_quest_stats', GetStopQuestStatsEndpoint, name='get_stop_quest_stats')
    app.router.add_view('/statistics_stop_quest', StatisticsStopQuestEndpoint, name='statistics_stop_quest')
    app.router.add_view('/get_noniv_encounters_count', GetNonivEncountersCountEndpoint,
                        name='get_noniv_encounters_count')
