# coding:utf-8
import collections
import logging
import math
import multiprocessing
import os
import secrets

from .util import *

log = logging.getLogger(__name__)

Location = collections.namedtuple('Location', ['lat', 'lng'])
ShortestDistance = collections.namedtuple('ShortestDistance', ['index', 'distance'])
GymInfoDistance = collections.namedtuple('GymInfoDistance', ['distance', 'location'])

Relation = collections.namedtuple('Relation', ['otherCoord', 'distance'])


def __midPoint(lat1, lon1, lat2, lon2):
    dLon = math.radians(lon2 - lon1)

    # convert to radians
    lat1 = math.radians(lat1)
    lat2 = math.radians(lat2)
    lon1 = math.radians(lon1)

    x = math.cos(lat2) * math.cos(dLon)
    y = math.cos(lat2) * math.sin(dLon);
    lat3 = math.atan2(math.sin(lat1) + math.sin(lat2), math.sqrt((math.cos(lat1) + x) * (math.cos(lat1) + x) + y * y));
    lon3 = lon1 + math.atan2(y, math.cos(lat1) + x);

    return Location(math.degrees(lat3), math.degrees(lon3))


def getDistanceOfTwoPointsInMeters(startLat, startLng, destLat, destLng):
    # approximate radius of earth in km
    R = 6373.0

    lat1 = math.radians(startLat)
    lon1 = math.radians(startLng)
    lat2 = math.radians(destLat)
    lon2 = math.radians(destLng)

    dlon = lon2 - lon1
    dlat = lat2 - lat1

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    distance = R * c

    distanceInMeters = distance * 1000
    return distanceInMeters


# returns a map of coords and all their closest neighbours based on a given radius * 2 (hence circles...)
def __getRelationsInRange(coordinates, rangeRadiusMeter):
    # print "Got " + str(len(coordinates)) + " coordinates and will build relations with radius " + str(rangeRadiusMeter)
    relations = {}
    for coord in coordinates:
        for otherCoord in coordinates:
            if coord.lat == otherCoord.lat and coord.lng == otherCoord.lng:
                if coord not in relations:
                    relations[coord] = []
            distance = getDistanceOfTwoPointsInMeters(coord.lat, coord.lng, otherCoord.lat, otherCoord.lng)
            if 0 <= distance <= rangeRadiusMeter * 2:
                if coord not in relations:
                    relations[coord] = []
                # we need to avoid duplicates...
                alreadyPresent = False
                for relation in relations[coord]:
                    if relation.otherCoord.lat == otherCoord.lat and relation.otherCoord.lng == otherCoord.lng:
                        alreadyPresent = True
                if not alreadyPresent:
                    relations[coord].append(Relation(otherCoord, distance))
    # print "Got " + str(len(relations)) + " relations"
    # print relations
    return relations


def __countOfGymsInCircle(middle, radius, relations):
    count = 1  # the origin of our relations is assumed to be in the circle anyway...
    for relation in relations:
        distance = getDistanceOfTwoPointsInMeters(middle.lat, middle.lng, relation.otherCoord.lat,
                                                  relation.otherCoord.lng)
        if distance <= radius:
            count += 1
    return count


# adapted from https://stackoverflow.com/questions/6671183/calculate-the-center-point-of-multiple-latitude-longitude-coordinate-pairs
def __getMiddleOfCoordList(listOfCoords):
    if len(listOfCoords) == 1:
        return listOfCoords[0]

    x = 0
    y = 0
    z = 0

    for coord in listOfCoords:
        # transform to radians...
        latRad = math.radians(coord.lat)
        lngRad = math.radians(coord.lng)

        x += math.cos(latRad) * math.cos(lngRad)
        y += math.cos(latRad) * math.sin(lngRad)
        z += math.sin(latRad)

    amountOfCoords = len(listOfCoords)
    x = x / amountOfCoords
    y = y / amountOfCoords
    z = z / amountOfCoords
    centralLng = math.atan2(y, x)
    centralSquareRoot = math.sqrt(x * x + y * y)
    centralLat = math.atan2(z, centralSquareRoot)

    return Location(math.degrees(centralLat), math.degrees(centralLng))


def __getCircle(coord, toBeInspected, relations, maxCount, maxDistance):
    # print "Next Circle with coord " + str(coord)
    # print "Relations: \n" + str(relations)
    # includedInCircle = [coord]
    includedInCircle = []
    # toBeInspected = relations[coord]
    if len(toBeInspected) == 0:
        # coord is alone at its position...
        return coord, []
    elif len(toBeInspected) == 1:
        # print "Just one coord, returning it as the middle: " + str(coord)
        return coord, [coord]
    # elif len(toBeInspected) == 2:
    #     for relation in toBeInspected:
    #         includedInCircle.append(relation.otherCoord)
    #     print "just two coords, returning the middle of " + str(coord) + " and " + str(relation.otherCoord)
    #     middle = __getMiddleOfCoordList(includedInCircle)
    #     print "Returning middle: " + str(middle) + " included in the circle: " + str(includedInCircle)
    #     return middle, includedInCircle

    # check if middle of the two farthest away already holds everything needed
    farthestAway, distanceToFarthest = __getFarthestInRelation(toBeInspected)
    allCoordsWithinRange = [coord, farthestAway]
    # for locationInUnion in unionOfFarthest:
    #     allCoordsWithinRange.append(locationInUnion)
    middle = __getMiddleOfCoordList(allCoordsWithinRange)
    countInside, coordsInCircle = __getCountAndCoordsInCircle(middle, relations, maxDistance)
    # print "Coords in circle basic middle: " + str(coordsInCircle) + " middle at: " + str(middle)
    # print "Relation inspected: " + str(toBeInspected)
    # print (len(coordsInCircle) == len(toBeInspected))
    # print "Count inside circle: " + str(countInside) + " maxCount: " + str(maxCount)
    if countInside <= maxCount and len(coordsInCircle) == len(toBeInspected):
        # print "Returning middle " + str(middle) + " and telling to remove " + str(coordsInCircle)
        return middle, coordsInCircle
    elif countInside > maxCount:
        toBeInspected = [toKeep for toKeep in toBeInspected if
                         not (toKeep.otherCoord.lat == farthestAway.lat
                              and toKeep.otherCoord.lng == farthestAway.lng)]
        return __getCircle(coord, toBeInspected, relations, maxCount, distanceToFarthest)
    else:
        return middle, coordsInCircle
        # TODO: calculate the entire stuff distributed by degrees north/south to coord


def __getMostSouthern(coord, relation):
    mostSouthern = coord
    for coordInRel in relation:
        if coordInRel.otherCoord.lat < mostSouthern.lat:
            mostSouthern = coordInRel.otherCoord
    return mostSouthern


def __listOfCoordsContainsCoord(listOfCoords, coord):
    # print "List to be searched: " + str(listOfCoords)
    # print "Coord to be searched for: " + str(coord)
    for coordOfList in listOfCoords:
        if coord.lat == coordOfList.lat and coord.lng == coordOfList.lng:
            return True
    return False


def __getMostNorthernInRelation(coord, relation):
    mostNorthern = coord
    for coordInRel in relation:
        if coordInRel.otherCoord.lat >= mostNorthern.lat:
            mostNorthern = coordInRel.otherCoord
    return mostNorthern


def __getMostWestAmongstRelations(relations):
    selected = list(relations.keys())[0]
    # print selected
    for relation in relations:
        if relation.lng < selected.lng:
            selected = relation
            # print selected
        elif relation.lng == selected.lng and relation.lat > selected.lat:
            selected = relation
            # print selected
    return selected


def __getFarthestInRelation(relation):
    distance = -1
    farthest = None
    for location in relation:
        if location.distance > distance:
            distance = location.distance
            farthest = location.otherCoord
    return farthest, distance


# only returns the union, not the points of origins of the two relations!
def __getUnionOfRelations(relationsOne, relationsTwo):
    listToReturn = []
    for relation in relationsOne:
        for otherRelation in relationsTwo:
            if (otherRelation.otherCoord.lat == relation.otherCoord.lat
                    and otherRelation.otherCoord.lng == relation.otherCoord.lng):
                listToReturn.append(otherRelation.otherCoord)
    return listToReturn


def __getCountAndCoordsInCircle(middle, relations, maxRadius):
    insideCircle = []
    for locationSource in relations:
        distance = getDistanceOfTwoPointsInMeters(middle.lat, middle.lng, locationSource.lat, locationSource.lng)
        if 0 <= distance <= maxRadius:
            insideCircle.append(locationSource)
    return len(insideCircle), insideCircle


def __sumUpRelations(relations, maxCountPerCircle, maxDistance):
    finalSet = []

    while len(relations) > 0:
        # get the most western north point in relations
        next = __getMostWestAmongstRelations(relations)
        # get a circle with "next" in it...
        middle, coordsToBeRemoved = __getCircle(next, relations[next], relations, maxCountPerCircle, maxDistance)
        # print "Removing: " + str(coordsToBeRemoved) + " Center of circle: " + str(middle)
        # remove the coords covered by the circle...
        finalSet.append(middle)
        relations = __removeCoordsFromRelations(relations, coordsToBeRemoved)
    return finalSet


def __removeCoordsFromRelations(relations, listOfCoords):
    for sourceLocation, distanceRelations in list(relations.items()):
        # iterate relations, remove anything matching listOfCoords
        for coord in listOfCoords:
            # print "Coord: " + str(coord) + " sourceLocation: " + str(sourceLocation)
            if coord.lat == sourceLocation.lat and coord.lng == sourceLocation.lng:
                # entire relation matches the coord, remove it
                relations.pop(sourceLocation)
                break
            # iterate through the entire distance relations...
            for distRel in distanceRelations:
                if distRel.otherCoord.lat == coord.lat and distRel.otherCoord.lng == coord.lng:
                    relations[sourceLocation].remove(distRel)
    return relations


def getLessCoords(npCoordinates, maxRadius, maxCountPerCircle):
    coordinates = []
    for coord in npCoordinates:
        coordinates.append(Location(coord[0].item(), coord[1].item()))

    relations = __getRelationsInRange(coordinates, maxRadius)
    summedUp = __sumUpRelations(relations, maxCountPerCircle, maxRadius)
    # print "Done summing up: " + str(summedUp) + " that's just " + str(len(summedUp))
    return summedUp


def __generate_new_solution(method, markov_steps, distmat, temp_current, cost_current, solution_current):
    # Constant Definitions
    NUM_NEW_SOLUTION_METHODS = 3
    SWAP, REVERSE, TRANSPOSE = 0, 1, 2

    sol_best = solution_current.copy()
    sol_current = solution_current.copy()
    cost_best = cost_current
    cost_cur = cost_current
    sol_new = solution_current.copy()
    for i in np.arange(markov_steps):
        if method == -1:
            # choice = np.random.randint(NUM_NEW_SOLUTION_METHODS)
            choice = secrets.randbelow(NUM_NEW_SOLUTION_METHODS)
        else:
            choice = method
        if choice == SWAP:
            sol_new = swap(sol_new)
        elif choice == REVERSE:
            sol_new = reverse(sol_new)
        elif choice == TRANSPOSE:
            sol_new = transpose(sol_new)
        else:
            # log.debug("ERROR: new solution method %d is not defined" % choice)
            exit(2)
        # Get the total distance of new route
        cost_new = sum_distmat(sol_new, distmat)

        if accept(cost_new, cost_cur, temp_current):
            # Update sol_current
            sol_current = sol_new.copy()
            cost_cur = cost_new
            # TODO: reduce iterator to get more rounds...
            if cost_new < cost_best:
                sol_best = sol_new.copy()
                cost_best = cost_new
        else:
            sol_new = sol_current.copy()

    return cost_best, sol_best.copy()


def get_index_array_numpy_compary(arr_orig, arr_new):
    indices = []
    length_arr = len(arr_orig)
    # log.error("Scanning range: %s" % str(length_arr))
    for i in range(length_arr):  # or range(len(theta))
        # log.info("Index: %s" % str(i))
        if np.array_equal(arr_new[i], arr_orig[i]):
            continue
        else:
            indices.append(i)
    return indices


def merge_results(arr_original, arr_first, arr_second):
    # if we cannot merge it, arr_first will be returned
    differences_first = get_index_array_numpy_compary(arr_original, arr_first)
    differences_second = get_index_array_numpy_compary(arr_original, arr_second)

    # check if first index of first is > last index of second and vice-versa
    if len(differences_first) == 0 and len(differences_second) == 0:
        return arr_original
    elif len(differences_second) == 0:
        merged_arr = arr_original.copy()
        for i in differences_first:
            merged_arr[i] = arr_first[i]
        return merged_arr
    elif len(differences_first) == 0:
        merged_arr = arr_original.copy()
        for i in differences_second:
            merged_arr[i] = arr_second[i]
        return merged_arr
    elif differences_first[0] > differences_second[-1]:
        # first index of 'first' is greater than last index of 'second', we can just merge it...
        # TODO
        merged_arr = arr_original.copy()
        for i in differences_first:
            merged_arr[i] = arr_first[i]
        for i in differences_second:
            merged_arr[i] = arr_second[i]
        return merged_arr
    elif differences_second[0] > differences_first[-1]:
        # first index of 'second' is greater than last index of 'first', we can merge without conflicts
        merged_arr = arr_original.copy()
        for i in differences_first:
            merged_arr[i] = arr_first[i]
        for i in differences_second:
            merged_arr[i] = arr_second[i]
        return merged_arr
    else:
        return arr_first


def getJsonRoute(coords, maxRadius, maxCoordsInRadius, routefile, num_processes=1, init_temp=100, halt=120, markov_coefficient=10):
    export_data = []
    if routefile is not None and os.path.isfile(routefile + '.calc'):
        log.info('Found existing Routefile')
        route = open(routefile + '.calc', 'r')
        for line in route:
            lineSplit = line.split(',')
            export_data.append({'lat': float(lineSplit[0].replace('\n', '')),
                                'lng': float(lineSplit[1].replace('\n', ''))})
        return export_data

    lessCoordinates = coords
    if len(coords) > 1 and maxRadius and maxCoordsInRadius:
        log.info("Calculating...")

        newCoords = getLessCoords(coords, maxRadius, maxCoordsInRadius)
        lessCoordinates = np.zeros(shape=(len(newCoords), 2))
        for i in range(len(lessCoordinates)):
            lessCoordinates[i][0] = newCoords[i][0]
            lessCoordinates[i][1] = newCoords[i][1]

        log.debug("Coords summed up: %s, that's just %s coords" % (str(lessCoordinates), str(len(lessCoordinates))))

    log.info("Got %s coordinates" % (len(lessCoordinates) / 2.0))
    if not len(lessCoordinates) > 2:
        log.info("less than 3 coordinates... not gonna take a shortest route on that")
        export_data = []
        for i in range(len(lessCoordinates)):
            export_data.append({'lat': lessCoordinates[i][0].item(),
                                'lng': lessCoordinates[i][1].item()})
        return export_data

    log.info("Calculating a short route through all those coords. Might take a while")
    # Constant Definitions
    NUM_NEW_SOLUTION_METHODS = 3
    SWAP, REVERSE, TRANSPOSE = 0, 1, 2

    coordinates = lessCoordinates.copy()
    # Params Initial
    num_location = coordinates.shape[0]
    markov_step = markov_coefficient * num_location
    T_0, T, T_MIN = init_temp, init_temp, 1
    T_NUM_CYCLE = 1

    # Build distance matrix to accelerate cost computing
    distmat = get_distmat(coordinates)

    # States: New, Current and Best
    sol_new, sol_current, sol_best = (np.arange(num_location),) * 3
    cost_new, cost_current, cost_best = (float('inf'),) * 3

    # Record costs during the process
    costs = []

    # previous cost_best
    prev_cost_best = cost_best

    # counter for detecting how stable the cost_best currently is
    cost_best_counter = 0

    # num_cores = multiprocessing.cpu_count()
    if num_processes != 1:
        from multiprocessing import Pool

        if num_processes > 1:
            num_cores = 1
        else:
            num_cores = multiprocessing.cpu_count()

        thread_pool = Pool(processes=num_cores)
    else:
        num_cores = 1
        thread_pool = None
    from timeit import default_timer as timer
    start = timer()

    # Simulated Annealing
    while T > T_MIN and cost_best_counter < halt:
        log.info("Still calculating... cost_best_counter: %s" % str(cost_best_counter))

        if num_cores and num_cores != 1 and thread_pool and cost_best_counter > 0:
            running_calculations = []
            full = secrets.randbelow(2)

            for i in range(num_cores):
                # method = np.random.randint(NUM_NEW_SOLUTION_METHODS)
                method = secrets.randbelow(NUM_NEW_SOLUTION_METHODS)
                if full == 0:
                    calculation = thread_pool.apply_async(__generate_new_solution, args=(method, int(round(markov_step / (num_cores * 2/3))), distmat, T,
                                                                                         cost_best, sol_best))
                elif cost_best_counter > halt * 0.3:
                    calculation = thread_pool.apply_async(__generate_new_solution,
                                                          args=(-1, markov_step, distmat, T,
                                                                cost_best, sol_best))
                else:
                    calculation = thread_pool.apply_async(__generate_new_solution,
                                                          args=(-1, int(round(markov_step / round(num_cores / 2))), distmat, T,
                                                                cost_best, sol_best))
                running_calculations.append(calculation)

            # thread_pool.close()
            # thread_pool.join()
            solutions_temp = []
            costs_temps = []
            for i in range(len(running_calculations)):
                # TODO: check this iteration, apparently only gets the first...
                cost_temp, solution_temp = running_calculations[i].get()

                if cost_temp < cost_best:
                    log.debug("Subprocess found better solution")
                    # cost_best = cost_temp
                    # sol_best = solution_temp.copy()
                    costs_temps.append(cost_temp)
                    solutions_temp.append(solution_temp.copy())
                else:
                    # log.info("Subprocess did not find a better solution")
                    cost_best_counter += 1
            # if costs_temps.count(costs_temps[0]) == len(costs_temps):
            #     cost_best_counter += 1

            # now check the better solutions if we can merge them ;)
            if len(costs_temps) == 0:
                log.warning("No better solution...")
            elif len(costs_temps) == 1:
                cost_best = costs_temps[0]
                sol_best = solutions_temp[0].copy()
            else:
                # multiple solutions, so much fun at once!
                merged_sol = sol_best.copy()
                length_sols_minus_one = len(solutions_temp) - 1
                # log.error("Length solutions minus one: %s" % str(length_sols_minus_one))
                range_to_be_searched = range(length_sols_minus_one)
                # log.error("Scanning range: %s" % str(range_to_be_searched))
                for i in range(len(solutions_temp) - 1):
                    merged_sol = merge_results(merged_sol, solutions_temp[i], solutions_temp[i + 1])
                    # TODO: if merged_sol == sol_best, check for the best solution in the set and use that...
                if np.array_equal(merged_sol, sol_best) or np.array_equal(merged_sol, solutions_temp[0]):
                    for i in range(len(costs_temps)):
                        if costs_temps[i] < cost_best:
                            cost_best = costs_temps[i]
                            sol_best = solutions_temp[i].copy()
                else:
                    sol_best = merged_sol.copy()
                    cost_best = sum_distmat(sol_best, distmat)
        else:
            cost_best, sol_best = __generate_new_solution(-1, int(round(num_location * 2)), distmat, T, cost_best, sol_best)

        # Lower the temperature
        alpha = 1 + math.log(1 + T_NUM_CYCLE + 1)
        T = T_0 / alpha
        costs.append(cost_best)

        # Increment T_NUM_CYCLE
        T_NUM_CYCLE += 1

        # Detect stability of cost_best
        if isclose(cost_best, prev_cost_best, abs_tol=1e-12):
            cost_best_counter += 1
        else:
            # Not stable yet, reset
            cost_best_counter = 0

        # Update prev_cost_best
        prev_cost_best = cost_best

        # Monitor the temperature & cost
        # log.debug("Temperature:", "%.2f°C" % round(T, 2),
        #      " Distance:", "%.2fm" % round(cost_best, 2),
        #      " Optimization Threshold:", "%d" % cost_best_counter)
    end = timer()
    if thread_pool is not None:
        thread_pool.close()
        thread_pool.join()
    log.info("Calculated route in %s minutes" % (str((end - start) / 60)))
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
