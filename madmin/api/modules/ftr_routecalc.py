from .. import apiHandler

def recalculate(route):
    # TODO
    # route.calculate_new_route(whole,bunch,of,crap)
    # this seems to be routemanager-specific information and we do not have access to that
    pass

class APIRouteCalc(apiHandler.ResourceHandler):
    component = 'routecalc'
    description = 'Add/Update/Delete routecalcs'
    implemented_methods = {
        'recalculate': recalculate
    }
