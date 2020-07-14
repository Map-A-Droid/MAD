import math
from mapadroid.utils.logging import logger, get_origin_logger
try:
    from ortools.constraint_solver import routing_enums_pb2
    from ortools.constraint_solver import pywrapcp
except Exception:
    pass


def create_data_model(lessCoordinates):
    """Stores the data for the problem."""

    data = {}

    # ortools requires x,y data to be integers
    # we will scale lat,lng to large numbers so that rounding won't adversely affect the path calculation
    data['locations'] = []
    for coord in lessCoordinates:
        data['locations'].append((int(float(coord[0]) * 1e9), int(float(coord[1]) * 1e9)))

    data['num_vehicles'] = 1  # calculate as if only one walker on route
    data['depot'] = 0  # route will start at the first lat,lng
    return data


def compute_euclidean_distance_matrix(locations):
    """Creates callback to return distance between points."""
    distances = {}
    for from_counter, from_node in enumerate(locations):
        distances[from_counter] = {}
        for to_counter, to_node in enumerate(locations):
            if from_counter == to_counter:
                distances[from_counter][to_counter] = 0
            else:
                # Euclidean distance
                distances[from_counter][to_counter] = (int(
                    math.hypot((from_node[0] - to_node[0]),
                               (from_node[1] - to_node[1]))))
    return distances


def format_solution(manager, routing, solution):
    """Format the solution for MAD."""
    route_through_nodes = []
    index = routing.Start(0)
    while not routing.IsEnd(index):
        route_through_nodes.append(manager.IndexToNode(index))
        index = solution.Value(routing.NextVar(index))
    return route_through_nodes


def route_calc_ortools(lessCoordinates, route_name):
    route_logger = get_origin_logger(logger, origin=route_name)
    data = create_data_model(lessCoordinates)

    # Create the routing index manager.
    manager = pywrapcp.RoutingIndexManager(len(data['locations']),
                                           data['num_vehicles'], data['depot'])

    # Create Routing Model.
    routing = pywrapcp.RoutingModel(manager)

    distance_matrix = compute_euclidean_distance_matrix(data['locations'])

    def distance_callback(from_index, to_index):
        """Returns the distance between the two nodes."""
        # Convert from routing variable Index to distance matrix NodeIndex.
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return distance_matrix[from_node][to_node]

    transit_callback_index = routing.RegisterTransitCallback(distance_callback)

    # Define cost of each arc.
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    # Setting first solution heuristic.
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)

    # Solve the problem.
    route_logger.debug("OR-Tools routecalc starting for route: {}", route_name)
    solution = routing.SolveWithParameters(search_parameters)
    route_logger.debug("OR-Tools routecalc finished for route: {}", route_name)

    return format_solution(manager, routing, solution)


def route_calc_all(lessCoordinates, route_name, num_processes, algorithm):
    route_logger = get_origin_logger(logger, origin=route_name)
    # check to see if we can use OR-Tools to perform our routecalc
    import platform
    if platform.architecture()[0] == "64bit" and algorithm == 'route':  # OR-Tools is only available for 64bit python
        route_logger.debug("64-bit python detected, checking if we can use OR-Tools")
        try:
            pywrapcp
            routing_enums_pb2
        except Exception:
            route_logger.debug("OR-Tools not available, using MAD routecalc")
        else:
            route_logger.debug("Using OR-Tools for routecalc")
            return route_calc_ortools(lessCoordinates, route_name)

    route_logger.debug("Using MAD quick routecalc")
    from mapadroid.route.routecalc.calculate_route_quick import route_calc_impl
    return route_calc_impl(lessCoordinates, route_name, num_processes)
