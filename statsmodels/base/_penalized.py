# -*- coding: utf-8 -*-
"""
Created on Sun May 10 08:23:48 2015

Author: Josef Perktold
License: BSD-3
"""

import numpy as np
from ._penalties import SCADSmoothed
from statsmodels.tools.numdiff import approx_fprime_cs, approx_fprime

class PenalizedMixin(object):
    """Mixin class for Maximum Penalized Likelihood

    Parameters
    ----------
    args and kwds for the model super class
    penal : None or instance of Penalized function class
        If penal is None, then currently SmoothedSCAD is used.
    pen_weight : float or None
        factor for weighting the penalization term.
        If None, then pen_weight is set to nobs.


    TODO: missing **kwds or explicit keywords

    TODO: do we adjust the inherited docstrings?
    We would need templating to add the penalization parameters

    """

    def __init__(self, *args, **kwds):

        # pop extra kwds before calling super
        self.penal = kwds.pop('penal', None)
        self.pen_weight =  kwds.pop('pen_weight', None)

        super(PenalizedMixin, self).__init__(*args, **kwds)

        # TODO: define pen_weight as average pen_weight? i.e. per observation
        # I would have prefered len(self.endog) * kwds.get('pen_weight', 1)
        # or use pen_weight_factor in signature
        if self.pen_weight is None:
            self.pen_weight = len(self.endog)
        # I keep the following instead of adding default in pop for future changes
        if self.penal is None:
            # TODO: switch to unpenalized by default
            self.penal = SCADSmoothed(0.1, c0=0.0001)

        self._init_keys.extend(['penal', 'pen_weight'])

    def loglike(self, params, pen_weight=None, **kwds):
        if pen_weight is None:
            pen_weight = self.pen_weight

        llf = super(PenalizedMixin, self).loglike(params, **kwds)
        if pen_weight != 0:
            llf -= pen_weight * self.penal.func(params)

        return llf


    def loglikeobs(self, params, pen_weight=None, **kwds):
        if pen_weight is None:
            pen_weight = self.pen_weight

        llf = super(PenalizedMixin, self).loglikeobs(params, **kwds)
        nobs_llf = float(llf.shape[0])

        if pen_weight != 0:
            llf -= pen_weight / nobs_llf * self.penal.func(params)

        return llf

    def score_numdiff(self, params, pen_weight=None, method='fd', **kwds):
        """score based on finite difference derivative

        """
        if pen_weight is None:
            pen_weight = self.pen_weight

        loglike = lambda p: self.loglike(p, pen_weight=pen_weight, **kwds)

        if method == 'cs':
            return approx_fprime_cs(params, loglike)
        elif method == 'fd':
            return approx_fprime(params, loglike, centered=True)
        else:
            raise ValueError('method not recognize, should be "fd" or "cs"')

    def score(self, params, pen_weight=None, **kwds):
        if pen_weight is None:
            pen_weight = self.pen_weight

        sc = super(PenalizedMixin, self).score(params, **kwds)
        if pen_weight != 0:
            sc -= pen_weight * self.penal.grad(params)

        return sc

    def score_obs(self, params, pen_weight=None, **kwargs):
        if pen_weight is None:
            pen_weight = self.pen_weight

        sc = super(PenalizedMixin, self).score_obs(params, **kwargs)
        nobs_sc = float(sc.shape[0])
        if pen_weight != 0:
            sc -= pen_weight / nobs_sc  * self.penal.grad(params)

        return sc

    def hessian_numdiff(self, params, pen_weight=None, **kwds):
        """hessian based on finite difference derivative

        """
        if pen_weight is None:
            pen_weight = self.pen_weight
        loglike = lambda p: self.loglike(p, pen_weight=pen_weight, **kwds)

        from statsmodels.tools.numdiff import approx_hess
        return approx_hess(params, loglike)

    def hessian(self, params, pen_weight=None, **kwds):
        if pen_weight is None:
            pen_weight = self.pen_weight

        hess = super(PenalizedMixin, self).hessian(params, **kwds)
        if pen_weight != 0:
            h = self.penal.deriv2(params)
            if h.ndim == 1:
                hess -= np.diag(pen_weight * h)
            else:
                hess -= pen_weight * h

        return hess

    def fit(self, method=None, trim=None, **kwds):
        """minimize negative penalized log-likelihood

        Parameters
        ----------
        method : None or str
            Method specifies the scipy optimizer as in nonlinear MLE models.
        trim : Boolean or float
            Default is False or None, which uses no trimming.
            If trim is True or a float, then small parameters are set to zero.
            If True, then a default threshold is used. If trim is a float, then
            it will be used as threshold.
            The default threshold is currently 1e-4, but it will change in
            future and become penalty function dependent.
        kwds : extra keyword arguments
            This keyword arguments are treated in the same way as in the
            fit method of the underlying model class.
            Specifically, additional optimizer keywords and cov_type related
            keywords can be added.

        """
        # If method is None, then we choose a default method ourselves

        # TODO: temporary hack, need extra fit kwds
        # we need to rule out fit methods in a model that will not work with
        # penalization
        if hasattr(self, 'family'):  # assume this identifies GLM
            kwds.update({'max_start_irls' : 0})

        # currently we use `bfgs` by default
        if method is None:
            method = 'bfgs'

        if trim is None:
            trim = False  # see below infinite recursion in `fit_constrained

        res = super(PenalizedMixin, self).fit(method=method, **kwds)

        if trim is False:
            # note boolean check for "is False" not evaluates to False
            return res
        else:
            if trim is True:
                trim = 1e-4  # trim threshold
            # TODO: make it penal function dependent
            # temporary standin, only works for Poisson and GLM,
            # and is computationally inefficient
            drop_index = np.nonzero(np.abs(res.params) < trim) [0]
            keep_index = np.nonzero(np.abs(res.params) > trim) [0]

            if drop_index.any():
                # TODO: do we need to add results attributes?
                res_aux = self._fit_zeros(keep_index, **kwds)
                return res_aux
            else:
                return res
