from mapadroid.utils.logging import get_logger, LoggerEnums


logger = get_logger(LoggerEnums.routemanager)


def route_calc_impl(coords, route_name, num_processes=1):
    with logger.contextualize(origin=route_name):
        less_coords_array = []
        for i in range(len(coords)):
            less_coords_array.append([coords[i][0].item(), coords[i][1].item()])

        length, path = tsp(less_coords_array)
        logger.info("Found {} long solution: ", length)

    return path


def tsp(data):
    logger.info("building the graph for a route of {}", len(data))
    # build a graph
    graph_data = build_graph(data)

    # build a minimum spanning tree
    logger.info("Building a min span tree..")
    min_span_tree = minimum_spanning_tree(graph_data)

    # find odd vertexes
    logger.info("Finding odd vertexes...")
    odd_vertexes = find_odd_vertexes(min_span_tree)

    # add minimum weight matching edges to MST
    logger.info("Adding minimum weight matching edges to MST...")
    minimum_weight_matching(min_span_tree, graph_data, odd_vertexes)

    # find an eulerian tour
    logger.info("Finding and Eulerian tour...")
    eulerian_tour = find_eulerian_tour(min_span_tree)

    current = eulerian_tour[0]
    path = [current]
    visited = [False] * len(eulerian_tour)
    visited[current] = True

    length = 0

    logger.info("Visiting each node in our eulerian tour and making a route")
    for node in eulerian_tour[1:]:
        if not visited[node]:
            path.append(node)
            visited[node] = True

            length += graph_data[current][node]
            current = node

    logger.info("Done making a route!")
    return length, path


def get_length(x1, y1, x2, y2):
    return ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** (1 / 2)


def build_graph(data):
    graph = {}
    for this in range(len(data)):
        for another_point in range(len(data)):
            if this != another_point:
                if this not in graph:
                    graph[this] = {}

                graph[this][another_point] = get_length(data[this][0], data[this][1], data[another_point][0],
                                                        data[another_point][1])

    return graph


class UnionFind:
    def __init__(self):
        self.weights = {}
        self.parents = {}

    def __getitem__(self, obj):
        if obj not in self.parents:
            self.parents[obj] = obj
            self.weights[obj] = 1
            return obj

        # find path of objects leading to the root
        path = [obj]
        root = self.parents[obj]
        while root != path[-1]:
            path.append(root)
            root = self.parents[root]

        # compress the path and return
        for ancestor in path:
            self.parents[ancestor] = root
        return root

    def __iter__(self):
        return iter(self.parents)

    def union(self, *objects):
        roots = [self[x] for x in objects]
        heaviest = max([(self.weights[r], r) for r in roots])[1]
        for root in roots:
            if root != heaviest:
                self.weights[heaviest] += self.weights[root]
                self.parents[root] = heaviest


def minimum_spanning_tree(graph):
    tree = []
    subtrees = UnionFind()
    for W, u, v in sorted((graph[u][v], u, v) for u in graph for v in graph[u]):  # noqa: VNE001 N806
        if subtrees[u] != subtrees[v]:
            tree.append((u, v, W))
            subtrees.union(u, v)

    return tree


def find_odd_vertexes(min_span_tree):
    tmp_g = {}
    vertexes = []
    for edge in min_span_tree:
        if edge[0] not in tmp_g:
            tmp_g[edge[0]] = 0

        if edge[1] not in tmp_g:
            tmp_g[edge[1]] = 0

        tmp_g[edge[0]] += 1
        tmp_g[edge[1]] += 1

    for vertex in tmp_g:
        if tmp_g[vertex] % 2 == 1:
            vertexes.append(vertex)

    return vertexes


def minimum_weight_matching(min_span_tree, graph, odd_vert):
    import random
    random.shuffle(odd_vert)

    while odd_vert:
        vertex = odd_vert.pop()
        length = float("inf")
        index = 1
        closest = 0
        for index in odd_vert:
            if vertex != index and graph[vertex][index] < length:
                length = graph[vertex][index]
                closest = index

        min_span_tree.append((vertex, closest, length))
        odd_vert.remove(closest)


def find_eulerian_tour(matched_min_span_tree):
    # find neigbours
    neighbours = {}
    for edge in matched_min_span_tree:
        if edge[0] not in neighbours:
            neighbours[edge[0]] = []

        if edge[1] not in neighbours:
            neighbours[edge[1]] = []

        neighbours[edge[0]].append(edge[1])
        neighbours[edge[1]].append(edge[0])

    # finds the hamiltonian circuit
    start_vertex = matched_min_span_tree[0][0]
    ep = [neighbours[start_vertex][0]]

    while len(matched_min_span_tree) > 0:
        for i, v in enumerate(ep):  # noqa: VNE001
            if len(neighbours[v]) > 0:
                break

        while len(neighbours[v]) > 0:
            w = neighbours[v][0]  # noqa: VNE001

            remove_edge_from_matched_mst(matched_min_span_tree, v, w)

            del neighbours[v][(neighbours[v].index(w))]
            del neighbours[w][(neighbours[w].index(v))]

            i += 1
            ep.insert(i, w)

            v = w  # noqa: VNE001

    return ep


def remove_edge_from_matched_mst(matched_mst, v1, v2):
    for i, item in enumerate(matched_mst):
        if (item[0] == v2 and item[1] == v1) or (item[0] == v1 and item[1] == v2):
            del matched_mst[i]

    return matched_mst
