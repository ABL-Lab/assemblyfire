# -*- coding: utf-8 -*-
"""
Class to get, hold, save and load connection matrix and sample submatrices
authors: Michael Reimann, András Ecker
last modified: 11.2020
"""

import h5py
from tqdm import tqdm
import numpy as np
import pandas
from assemblyfire.assemblies import Assembly


class ConnectivityMatrix(object):
    """Small utility class to hold a connections matrix and generate submatrices"""
    def __init__(self, adj_matrix, gids):
        self._m = adj_matrix
        self._gids = gids
        self._lookup = self.__make_lookup__()

    def __make_lookup__(self):
        return pandas.Series(np.arange(len(self._gids)), index=self._gids)

    @property
    def matrix(self):
        return self._m

    @property
    def dense_matrix(self):
        return self._m.todense()

    @property
    def array(self):
        return np.array(self.dense_matrix)

    @staticmethod
    def __extract_gids__(an_obj):
        if isinstance(an_obj, Assembly):
            return an_obj.gids
        return an_obj

    def submatrix(self, sub_gids, sub_gids_post=None):
        """
        Return a submatrix
        :param sub_gids: Subpopulation to get the submatrix for. Can be either a list of gids, or an Assembly object
        :param sub_gids_post: (optiona) if specified, defines the postsynaptic population. Else pre- equals postsynaptic
        population
        :return: the adjacency submatrix of the specified population(s).
        """
        if sub_gids_post is not None:
            return self._m[np.ix_(self._lookup[self.__extract_gids__(sub_gids)],
                                     self._lookup[self.__extract_gids__(sub_gids_post)])]
        idx = self._lookup[self.__extract_gids__(sub_gids)]
        return self._m[np.ix_(idx, idx)]

    def dense_submatrix(self, sub_gids, sub_gids_post=None):
        return self.submatrix(sub_gids, sub_gids_post=sub_gids_post).todense()

    def subarray(self, sub_gids, sub_gids_post=None):
        return np.array(self.dense_submatrix(sub_gids, sub_gids_post=sub_gids_post))

    @classmethod
    def from_bluepy(cls, cfg, gids=None):
        from assemblyfire.spikes import get_bluepy_simulation
        from scipy import sparse
        sim = get_bluepy_simulation(cfg)
        if gids is None:
            from assemblyfire.utils import get_E_gids
            gids = get_E_gids(sim.circuit, sim.target)

        conv = pandas.Series(np.arange(len(gids)), index=gids)
        indptr = [0]
        indices = []

        for gid in tqdm(gids, desc="Building connectivity matrix", miniters=len(gids) / 100):
            aff = conv[np.intersect1d(sim.circuit.connectome.afferent_gids(gid), gids)]
            indices.extend(aff)
            indptr.append(len(indices))
        data = np.ones_like(indices, dtype=bool)
        adj_mat = sparse.csc_matrix((data, indices, indptr), shape=(len(gids), len(gids)))
        return cls(adj_mat, gids)

    @classmethod
    def from_h5(cls, fn, group_name, prefix=None):
        from scipy import sparse
        if prefix is None:
            prefix = "connectivity"
        with h5py.File(fn, 'r') as h5:
            prefix_grp = h5[prefix]
            data_grp = prefix_grp[group_name]
            data = data_grp["data"][:]
            indices = data_grp["indices"][:]
            indptr = data_grp["indptr"][:]
            gids = data_grp["gids"][:]
            adj_mat = sparse.csc_matrix((data, indices, indptr), shape=(len(gids), len(gids)))
            return cls(adj_mat, gids)

    def to_h5(self, fn, prefix=None):
        if prefix is None:
            prefix = "connectivity"
        with h5py.File(fn, "a") as h5:
            prefix_grp = h5.require_group(prefix)
            data_grp = prefix_grp.create_group("matrix")  # TODO: not overly hard coded
            data_grp.create_dataset("data", data=self._m.data)
            data_grp.create_dataset("indices", data=self._m.indices)
            data_grp.create_dataset("indptr", data=self._m.indptr)
            data_grp.create_dataset("gids", data=self._gids)

