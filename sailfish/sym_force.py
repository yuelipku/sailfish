"""Symbolic processing of body forces."""

__author__ = 'Michal Januszewski'
__email__ = 'sailfish-cfd@googlegroups.com'
__license__ = 'LGPL3'

import operator

from mako.runtime import Undefined
import sympy
from sympy import Matrix, Symbol

from sailfish.sym import poly_factorize, S

def needs_coupling_accel(i, force_couplings):
    """Returns True is a grid is coupled to any other grid.

    :param i: grid ID
    :param force_couplings: see fluid_accel()
    """
    if type(force_couplings) is Undefined:
        return False
    return (i in
        reduce(lambda x, y: operator.add(x, [y[0], y[1]]), force_couplings.keys(), []))

def needs_accel(i, forces, force_couplings):
    """Returns True if there a force acting on a grid.

    :param i: grid ID
    :param forces: see fluid_accel()
    :param force_couplings: see fluid_accel()
    """
    if type(forces) is Undefined:
        return False

    return (i in forces) or needs_coupling_accel(i, force_couplings)

def accel_vector(grid, grid_num):
    eax = getattr(S, 'g%seax' % grid_num)
    eay = getattr(S, 'g%seay' % grid_num)
    eaz = getattr(S, 'g%seaz' % grid_num)

    # TODO: Move this block to another function.
    if grid.dim == 2:
        ea = Matrix(([eax, eay],))
    else:
        ea = Matrix(([eax, eay, eaz],))

    return ea

def fluid_accel(sim, i, axis, forces, force_couplings):
    """
    :param sim: simulation object
    :param i: grid ID
    :param axis: base axis for the output vector
    :param forces: dict: grid ID -> dict(accel -> value); accel is a boolean
        indicating whether value is a force or acceleration
    :param force_couplings: dict mapping pairs of grid IDs to the name of a
        Shan-Chen coupling constant
    """
    if forces is not Undefined and needs_accel(i, forces, force_couplings):
        ea = accel_vector(sim.grid, i)
        return ea[axis]
    else:
        return 0.0

def body_force_accel(i, dim, forces, accel=True):
    """
    :param i: grid number
    :param forces: forces dictionary (see lbm.py)
    :param accel: if True, returns an acceleration expression; returns a force
            expresssion otherwise
    """
    t = 0

    if i in forces:
        # Force
        if False in forces[i]:
            if accel:
                t += forces[i][False][dim] / Symbol('g%dm0' % i)
            else:
                t += forces[i][False][dim]
        # Acceleration
        if True in forces[i]:
            if accel:
                t += forces[i][True][dim]
            else:
                t += forces[i][True][dim] * Symbol('g%dm0' % i)

    return t

def bgk_external_force(grid, grid_num=0):
    """Get expressions for the external body force correction in the BGK model.

    This implements the external force as in Eq. 20 from PhysRevE 65, 046308.

    :param grid: the grid class to be used

    :rtype: list of sympy expressions (in the same order as the current grid's basis)
    """
    pref = Symbol('pref')

    ea = accel_vector(grid, grid_num)
    ret = []

    for i, ei in enumerate(grid.basis):
        t = pref * grid.weights[i] * poly_factorize((ei - grid.v + ei.dot(grid.v)*ei*3).dot(ea))
        ret.append((t, grid.idx_name[i]))

    return ret

def bgk_external_force_pref(grid_num=0):
    # FIXME: This includes a factor of c_s^2.
    rho = getattr(S, 'g%sm0' % grid_num)

    if grid_num == 0:
        rho = 'rho'
    else:
        rho = 'phi'

    # This includes a density factor as the device code always computes
    # accelerations, not forces.
    return '%s * 3.0f * (1.0f - 1.0f/(2.0f * tau%s))' % (rho, grid_num)

def free_energy_external_force(sim, grid_num=0):
    """Creates expressions for the external body force term in the free-energy model.

    This implements the external force as in Eq. 2.13 from Halim Kusumaatmaja's PhD
    thesis ("Lattice Boltzmann Studies of Wetting and Spreading on Patterned Surfaces").
    """
    grid = sim.grid
    # TODO: verify if this needs to be an accel or force vector;
    # add references
    ea = accel_vector(grid, grid_num)
    ret = []
    sum_ = 0

    S = sim.S
    for i, ei in enumerate(grid.basis[1:]):
        t = S.wi[i] * (ea.dot(ei) * (1 + 3 * ei.dot(grid.v)) - ea.dot(grid.v))
        sum_ += t
        ret.append((t, grid.idx_name[i+1]))

    ret = [(sympy.simplify(-sum_), grid.idx_name[0])] + ret
    return ret
