import asyncio
import concurrent.futures
from typing import List, Tuple, Optional

from loguru import logger

from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.db.helper import SettingsRoutecalcHelper
from mapadroid.db.model import SettingsRoutecalc
from mapadroid.route.routecalc.ClusteringHelper import ClusteringHelper
from mapadroid.utils.DatetimeWrapper import DatetimeWrapper
from mapadroid.utils.collections import Location
from mapadroid.utils.madGlobals import RoutecalculationTypes


class RoutecalcUtil:
    @staticmethod
    async def calculate_route(db_wrapper: DbWrapper, routecalc_id: int, coords: List[Location], max_radius,
                              max_coords_within_radius,
                              load_persisted_route, algorithm: RoutecalculationTypes,
                              use_s2, s2_level, route_name,
                              overwrite_persisted_route: bool = False) -> list[Location]:
        async with db_wrapper as session, session:
            routecalc_entry: Optional[SettingsRoutecalc] = await SettingsRoutecalcHelper.get(session, routecalc_id)
            if load_persisted_route and routecalc_entry:
                saved_route: list[Location] = RoutecalcUtil.read_persisted_route(routecalc_entry)
                if saved_route:
                    logger.debug('Using routefile from DB')
                    return saved_route

            if not routecalc_entry:
                #  Missing instance_id...
                routecalc_entry = SettingsRoutecalc()
                routecalc_entry.routecalc_id = routecalc_id
                routecalc_entry.instance_id = db_wrapper.get_instance_id()

            routecalc_entry.recalc_status = 1
            # Commit to make the recalc_status visible to others
            session.add(routecalc_entry)

            try:
                await session.commit()
            except Exception as e:
                logger.exception(e)
                await session.rollback()

        calculated_route: list[Location] = []
        if use_s2:
            logger.debug("Using S2 method for calculation with S2 level: {}", s2_level)

        if len(coords) > 0 and max_radius and max_radius >= 1 and max_coords_within_radius:
            logger.info("Calculating route for {}", route_name)
            loop = asyncio.get_running_loop()
            with concurrent.futures.ThreadPoolExecutor() as pool:
                calculated_route = await loop.run_in_executor(
                    pool, RoutecalcUtil.get_less_coords, coords, max_radius, max_coords_within_radius, use_s2,
                    s2_level)

            logger.debug("Coords summed up to {} coords", len(calculated_route))
        logger.debug("Got {} coordinates", len(calculated_route))
        if len(calculated_route) < 3:
            logger.debug("less than 3 coordinates... not gonna take a shortest route on that")
        else:
            logger.info("Calculating a short route through all those coords. Might take a while")
            from timeit import default_timer as timer
            start = timer()
            from mapadroid.route.routecalc.calculate_route_all import \
                route_calc_all
            loop = asyncio.get_running_loop()
            with concurrent.futures.ThreadPoolExecutor() as pool:
                sol_best = await loop.run_in_executor(
                    pool, route_calc_all, calculated_route, route_name, algorithm)

            end = timer()

            calc_dur = (end - start) / 60
            time_unit = 'minutes'
            if calc_dur < 1:
                calc_dur = int(calc_dur * 60)
                time_unit = 'seconds'

            logger.info("Calculated route for {} in {} {}", route_name, calc_dur, time_unit)
            calculated_route_old = calculated_route
            calculated_route = []
            for i in range(len(sol_best)):
                calculated_route.append(calculated_route_old[int(sol_best[i])])
        async with db_wrapper as session, session:
            routecalc_entry: Optional[SettingsRoutecalc] = await SettingsRoutecalcHelper.get(session, routecalc_id)
            if overwrite_persisted_route:
                await RoutecalcUtil._write_route_to_db_entry(routecalc_entry, calculated_route)
                routecalc_entry.last_updated = DatetimeWrapper.now()
            routecalc_entry.recalc_status = 0

            session.add(routecalc_entry)
            try:
                await session.commit()
            except Exception as e:
                logger.exception(e)
                await session.rollback()
        return calculated_route

    @staticmethod
    async def _write_route_to_db_entry(routecalc_entry: SettingsRoutecalc,
                                       new_route: list[Location]) -> None:
        calc_coords = []
        for coord in new_route:
            calc_coord = '%s,%s' % (coord.lat, coord.lng)
            calc_coords.append(calc_coord)
        # Only save if we aren't calculating in memory
        to_be_written = str(calc_coords).replace("\'", "\"")
        routecalc_entry.routefile = to_be_written

    @staticmethod
    def get_less_coords(coords: List[Location], max_radius: int, max_coords_within_radius: int,
                        use_s2: bool = False, s2_level: int = 15):
        """
        Clusters the coords inserted according to the parameters provided
        Args:
            coords:
            max_radius:
            max_coords_within_radius:
            use_s2:
            s2_level:

        Returns:

        """

        coords_cleaned_up: List[Location] = []
        if max_radius > 1:
            # Hardly feasible to cluster a distance of less than 1m...
            coordinates: List[Tuple[int, Location]] = []
            for coord in coords:
                coordinates.append(
                    (0, coord)
                )
            clustering_helper = ClusteringHelper(max_radius=max_radius, max_count_per_circle=max_coords_within_radius,
                                                 max_timedelta_seconds=0, use_s2=use_s2, s2_level=s2_level)
            clustered_events = clustering_helper.get_clustered(coordinates)
            for event in clustered_events:
                coords_cleaned_up.append(event[1])
        else:
            coords_cleaned_up = coords
        return coords_cleaned_up

    @staticmethod
    def read_saved_json_route(routecalc_entry: SettingsRoutecalc):
        result = []
        if routecalc_entry.routefile and routecalc_entry.routefile.strip():
            for line in routecalc_entry.routefile.split("\","):
                line = line.replace("\"", "").replace("]", "").replace("[", "").strip()
                if not line:
                    continue
                line_split = line.split(',')
                result.append({'lat': float(line_split[0].strip()), 'lng': float(line_split[1].strip())})
        return result

    @staticmethod
    def read_persisted_route(routecalc_entry: SettingsRoutecalc) -> list[Location]:
        result: list[Location] = []
        if routecalc_entry.routefile and routecalc_entry.routefile.strip():
            for line in routecalc_entry.routefile.split("\","):
                line = line.replace("\"", "").replace("]", "").replace("[", "").strip()
                if not line:
                    continue
                line_split = line.split(',')
                result.append(Location(float(line_split[0].strip()), float(line_split[1].strip())))
        return result
