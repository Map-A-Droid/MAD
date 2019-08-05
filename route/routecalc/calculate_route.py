# coding:utf-8
import math
import multiprocessing
import os
import secrets

from route.routecalc.ClusteringHelper import ClusteringHelper
from utils.collections import Location
from utils.logging import logger

from .util import *


def getLessCoords(npCoordinates, maxRadius, maxCountPerCircle, useS2: bool=False, S2level: int=15):
    coordinates = []
    for coord in npCoordinates:
        coordinates.append(
            (0, Location(coord[0].item(), coord[1].item()))
        )

    clustering_helper = ClusteringHelper(max_radius=maxRadius, max_count_per_circle=maxCountPerCircle,
                                         max_timedelta_seconds=0, useS2=useS2, S2level=S2level)
    clustered_events = clustering_helper.get_clustered(coordinates)
    # relations = __getRelationsInRange(coordinates, maxRadius)
    # summedUp = __sumUpRelations(relations, maxCountPerCircle, maxRadius)
    coords_cleaned_up = []
    for event in clustered_events:
        coords_cleaned_up.append(
            event[1]
        )

    # print "Done summing up: " + str(summedUp) + " that's just " + str(len(summedUp))
    return coords_cleaned_up


def getJsonRoute(coords, maxRadius, maxCoordsInRadius, routefile, num_processes=1, algorithm='optimized', useS2: bool = False, S2level: int=15):
    export_data = []
    if useS2: logger.debug("Using S2 method for calculation with S2 level: {}", S2level)
    if routefile is not None and os.path.isfile(routefile + '.calc'):
        logger.debug('Found existing routefile {}', routefile)
        with open(routefile + '.calc', 'r') as route:
            for line in route:
                # skip empty lines
                if not line.strip():
                    continue

                lineSplit = line.split(',')
                export_data.append({'lat': float(lineSplit[0].strip()),
                                    'lng': float(lineSplit[1].strip())})
        return export_data

    lessCoordinates = coords
    if len(coords) > 1 and maxRadius and maxCoordsInRadius:
        logger.info("Calculating...")

        newCoords = getLessCoords(coords, maxRadius, maxCoordsInRadius, useS2, S2level)
        lessCoordinates = np.zeros(shape=(len(newCoords), 2))
        for i in range(len(lessCoordinates)):
            lessCoordinates[i][0] = newCoords[i][0]
            lessCoordinates[i][1] = newCoords[i][1]

        logger.debug("Coords summed up: {}, that's just {} coords",
                     str(lessCoordinates), str(len(lessCoordinates)))

    logger.debug("Got {} coordinates", len(lessCoordinates))
    if len(lessCoordinates) < 3:
        logger.debug(
            "less than 3 coordinates... not gonna take a shortest route on that")
        export_data = []
        for i in range(len(lessCoordinates)):
            export_data.append({'lat': lessCoordinates[i][0].item(),
                                'lng': lessCoordinates[i][1].item()})
        return export_data

    logger.info(
        "Calculating a short route through all those coords. Might take a while")
    from timeit import default_timer as timer
    start = timer()

    if algorithm == 'quick':
        from route.routecalc.calculate_route_quick import route_calc_impl
    else:
        from route.routecalc.calculate_route_optimized import route_calc_impl

    sol_best = route_calc_impl(lessCoordinates, num_processes)

    end = timer()
    logger.info("Calculated route in {} minutes", str((end - start) / 60))
    # plot(sol_best.tolist(), coordinates, costs)

    for i in range(len(sol_best)):
        if routefile is not None:
            with open(routefile + '.calc', 'a') as f:
                f.write(str(lessCoordinates[int(sol_best[i])][0].item()) + ', ' + str(
                    lessCoordinates[int(sol_best[i])][1].item()) + '\n')
        export_data.append({'lat': lessCoordinates[int(sol_best[i])][0].item(),
                            'lng': lessCoordinates[int(sol_best[i])][1].item()})

    # return json.dumps(export_data)
    return export_data


