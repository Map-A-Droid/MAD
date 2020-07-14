import numpy as np


def isclose(point_a, point_b, rel_tol=1e-09, abs_tol=0.0):
    return abs(point_a - point_b) <= max(rel_tol * max(abs(point_a), abs(point_b)), abs_tol)


def sum_distmat(polygon, distmat):
    dist = 0
    num_location = polygon.shape[0]
    for index in range(num_location - 1):
        dist += distmat[polygon[index]][polygon[index + 1]]
    dist += distmat[polygon[0]][polygon[num_location - 1]]
    return dist


def get_distmat(polygon):
    num_location = polygon.shape[0]
    # 1 degree of lat/lon ~ 111km = 111000m in Taiwan
    polygon *= 111000
    distmat = np.zeros((num_location, num_location))
    for index in range(num_location):
        for sub_ind in range(index, num_location):
            distmat[index][sub_ind] = distmat[sub_ind][index] = np.linalg.norm(polygon[index] - polygon[sub_ind])
    return distmat


def swap(sol_new):
    while True:
        n1 = np.int(np.floor(np.random.uniform(0, sol_new.shape[0])))
        n2 = np.int(np.floor(np.random.uniform(0, sol_new.shape[0])))
        if n1 != n2:
            break
    sol_new[n1], sol_new[n2] = sol_new[n2], sol_new[n1]
    return sol_new


def reverse(sol_new):
    while True:
        n1 = np.int(np.floor(np.random.uniform(0, sol_new.shape[0])))
        n2 = np.int(np.floor(np.random.uniform(0, sol_new.shape[0])))
        if n1 != n2:
            break
    sol_new[n1:n2] = sol_new[n1:n2][::-1]

    return sol_new


def transpose(sol_new):
    while True:
        n1 = np.int(np.floor(np.random.uniform(0, sol_new.shape[0])))
        n2 = np.int(np.floor(np.random.uniform(0, sol_new.shape[0])))
        n3 = np.int(np.floor(np.random.uniform(0, sol_new.shape[0])))
        if n1 != n2 != n3 != n1:
            break
    # Let n1 < n2 < n3
    n1, n2, n3 = sorted([n1, n2, n3])

    # Insert data between [n1,n2) after n3
    tmplist = sol_new[n1:n2].copy()
    sol_new[n1: n1 + n3 - n2 + 1] = sol_new[n2: n3 + 1].copy()
    sol_new[n3 - n2 + 1 + n1: n3 + 1] = tmplist.copy()
    return sol_new


def accept(cost_new, cost_current, T):
    # If new cost better than current, accept it
    # If new cost not better than current, accept it by probability P(dE)
    # P(dE) = exp(dE/(kT)), defined by Metropolis
    return (cost_new <= cost_current or
            np.random.rand() <= np.exp(-(cost_new - cost_current) / T))
