# -*- coding: utf-8 -*-
"""
Assembly detection related utility functions
(mostly loading simulation related stuff)
author: András Ecker, last update: 12.2020
"""

import os
import json
import h5py
from collections import namedtuple
import numpy as np

SpikeMatrixResult = namedtuple("SpikeMatrixResult", ["spike_matrix", "gids", "t_bins"])
SingleCellFeatures = namedtuple("SingleCellFeatures", ["gids", "r_spikes", "mean_ts", "std_ts"])


def _get_bluepy_circuit(circuitconfig_path):
    try:
        from bluepy.v2 import Circuit
    except ImportError as e:
        msg = (
            "Assemblyfire requirements are not installed.\n"
            "Please pip install bluepy as follows:\n"
            " pip install -i https://bbpteam.epfl.ch/repository/devpi/simple bluepy[all]"
        )
        raise ImportError(str(e) + "\n\n" + msg)
    return Circuit(circuitconfig_path)


def ensure_dir(dirpath):
    if not os.path.exists(dirpath):
        os.makedirs(dirpath)


def get_seeds(root_path):
    """Reads sim seeds from simwriter generated file"""
    f_name = os.path.join(root_path, "project_simulations.txt")
    with open(f_name, "r") as f:
        seeds = [int(l.strip().split('/')[-1][4:]) for l in f]
    return seeds


def get_patterns(patterns_fname):
    """Return list of patterns presented during the simulation"""
    with open(patterns_fname, "r") as f:
        patterns = [line.strip() for line in f]
    return patterns


def _get_gids(c, target):
    import warnings
    warnings.simplefilter(action="ignore", category=FutureWarning)
    return c.cells.ids({"$target": target})


def get_E_gids(c, target="mc2_Column"):
    from bluepy.v2.enums import Cell
    import warnings
    warnings.simplefilter(action="ignore", category=FutureWarning)
    return c.cells.ids({"$target": target, Cell.SYNAPSE_CLASS: "EXC"})


def get_EI_gids(c, target="mc2_Column"):
    from bluepy.v2.enums import Cell
    import warnings
    warnings.simplefilter(action="ignore", category=FutureWarning)
    gidsE = get_E_gids(c, target)
    gidsI = c.cells.ids({"$target": target, Cell.SYNAPSE_CLASS: "INH"})
    return gidsE, gidsI


def _get_layer_gids(c, layer, target):
    from bluepy.v2.enums import Cell
    import warnings
    warnings.simplefilter(action="ignore", category=FutureWarning)
    return c.cells.ids({"$target": target, Cell.LAYER: layer})


def get_mtypes(c, gids):
    return c.cells.get(gids)["mtype"]


def get_depths(c, gids):
    return c.cells.get(gids)["y"]


def map_gids_to_depth(circuit_config, gids=[], target="mc2_Column"):
    """Creates gid-depth map (for better figure asthetics)"""

    c = _get_bluepy_circuit(circuit_config)
    if not len(gids):
        gids = _get_gids(c, target)
    ys = c.cells.get(gids)["y"]
    # convert pd.Series to dictionary...
    gids = np.asarray(ys.index)
    depths = ys.values
    return {gid: depths[i] for i, gid in enumerate(gids)}


def get_layer_boundaries(circuit_config, target="mc2_Column"):
    """Gets layer boundaries and cell numbers (used for raster plots)"""

    c = _get_bluepy_circuit(circuit_config)
    yticks = []
    yticklables = []
    hlines = []
    for layer in range(1, 7):
        gids = _get_layer_gids(c, layer, target)
        yticklables.append("L%i\n(%i)" % (layer, len(gids)))
        ys = c.cells.get(gids)["y"]
        yticks.append(ys.mean())
        if layer == 1:
            hlines.append(ys.max())
            hlines.append(ys.min())
        else:
            hlines.append(ys.min())
    return {"yticks": yticks, "yticklabels": yticklables, "hlines": hlines}


def get_spikes(sim, gids, t_start, t_end):
    """Extracts spikes (using bluepy)"""

    if gids is None:
        spikes = sim.spikes.get(t_start=t_start, t_end=t_end)
    else:
        spikes = sim.spikes.get(gids, t_start=t_start, t_end=t_end)
    return np.asarray(spikes.index), np.asarray(spikes.values)


def load_assemblies_from_h5(h5f_name, prefix="assemblies", load_metadata=False):
    """Load assemblies over seeds from saved h5 file into dict of AssemblyGroups"""
    from assemblyfire.assemblies import AssemblyGroup, AssemblyProjectMetadata

    with h5py.File(h5f_name, "r") as h5f:
        seeds = list(h5f[prefix].keys())
    assembly_grp_dict = {seed: AssemblyGroup.from_h5(h5f_name, seed, prefix=prefix) for seed in seeds}
    if load_metadata:
        project_metadata = AssemblyProjectMetadata.from_h5(h5f_name, prefix="spikes")
        return assembly_grp_dict, project_metadata
    else:
        return assembly_grp_dict


def load_consensus_assemblies_from_h5(h5f_name, prefix="consensus", load_metadata=False):
    """Load consensus (clustered and thresholded )assemblies
    from saved h5 file into dict of ConsensusAssembly objects"""
    from assemblyfire.assemblies import ConsensusAssembly, AssemblyProjectMetadata

    with h5py.File(h5f_name, "r") as h5f:
        keys = list(h5f[prefix].keys())
    assembly_grp_dict = {k: ConsensusAssembly.from_h5(h5f_name, k, prefix=prefix) for k in keys}
    if load_metadata:
        project_metadata = AssemblyProjectMetadata.from_h5(h5f_name, prefix="spikes")
        return assembly_grp_dict, project_metadata
    else:
        return assembly_grp_dict


def load_spikes_from_h5(h5f_name, prefix="spikes"):
    """Load spike matrices over seeds from saved h5 file"""
    from assemblyfire.assemblies import AssemblyProjectMetadata

    h5f = h5py.File(h5f_name, "r")
    seeds = list(h5f[prefix].keys())
    prefix_grp = h5f[prefix]
    spike_matrix_dict = {}
    for seed in seeds:
        spike_matrix_dict[seed] = SpikeMatrixResult(prefix_grp[seed]["spike_matrix"][:],
                                                    prefix_grp[seed]["gids"][:],
                                                    prefix_grp[seed]["t_bins"][:])
    h5f.close()
    project_metadata = AssemblyProjectMetadata.from_h5(h5f_name, prefix=prefix)
    return spike_matrix_dict, project_metadata


def load_single_cell_features_from_h5(h5f_name, prefix="spikes"):
    """Load spike matrices over seeds from saved h5 file"""
    from assemblyfire.assemblies import AssemblyProjectMetadata

    h5f = h5py.File(h5f_name, "r")
    prefix_grp = h5f[prefix]
    single_cell_features = SingleCellFeatures(prefix_grp["gids"][:], prefix_grp["r_spikes"][:],
                                              prefix_grp["mean_ts_in_bin"][:], prefix_grp["std_ts_in_bin"][:])
    h5f.close()
    project_metadata = AssemblyProjectMetadata.from_h5(h5f_name, prefix=prefix)
    return single_cell_features, project_metadata


def all_equal(lst, ref=None):
    """Return: True for empty lst
    if ref != None return: True if all of its elements are equal to ref, False otherwise.
    if ref == None return: True if all elements for lst are equal to each other, False otherwise"""
    if ref is not None:
        iterator = iter([ref]+lst)
    else:
        iterator = iter(lst)
    try:
        first = next(iterator)
    except StopIteration:
        return True
    return all(first == rest for rest in iterator)
