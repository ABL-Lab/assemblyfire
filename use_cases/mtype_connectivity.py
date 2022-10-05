"""
Slightly modified (from assemblyfire's general E->E connectivity) script
to investigate E->I innervation
last modified: András Ecker 10.2022
"""

import os
import numpy as np
from conntility.circuit_models.neuron_groups import load_filter
from conntility.circuit_models import circuit_connection_matrix

import assemblyfire.utils as utils
from assemblyfire.config import Config
from assemblyfire.plots import plot_in_degrees


def _load_single_assembly_grp(h5f_name, prefix):
    assembly_grp_dict, _ = utils.load_assemblies_from_h5(h5f_name, prefix)
    seeds = list(assembly_grp_dict.keys())
    assert len(seeds) == 1, "Expected a single assembly group under a single seed saved..."
    return seeds[0], assembly_grp_dict[seeds[0]]


def get_indegrees(conn_mat, gids, all_gids):
    """Indexes (pres)synaptic `gids` and returns in degrees (of postsynaptic gids)"""
    idx = np.in1d(all_gids, gids, assume_unique=True)
    return np.array(conn_mat[idx].sum(axis=0)).flatten()


def get_mtype_indegree(config, post_mtype, plot_txt="PC-MC"):
    """Loads in assemblies and for each of them plots their in degree distr. on selected `post_mtype`"""

    # get connectivity matrix (in conntility's format to be able to generate control models later)
    sim = utils.get_bluepy_simulation(utils.get_sim_path(config.root_path).iloc[0])
    c = sim.circuit
    load_cfg = {"loading": {"base_target": config.target, "properties": ["x", "y", "z", "mtype"],
                            "atlas": [{"data": "[PH]y", "properties": ["[PH]y"]}]}}
    pre_nrn = load_filter(c, load_cfg)
    pre_gids = pre_nrn["gid"].to_numpy()
    post_gids = utils.get_mtype_gids(c, sim.target, post_mtype)
    conn_mat = circuit_connection_matrix(c, for_gids=pre_gids, for_gids_post=post_gids).tocsr()

    # get in degrees from assemblies and controls (mimicking the structure of `topology.py/in_degree_assemblies()`)
    seed, assembly_grp = _load_single_assembly_grp(config.h5f_name, config.h5_prefix_assemblies)
    in_degrees, ind_ctrl = {}, {"n": {}, "depths": {}, "mtypes": {}}
    for assembly in assembly_grp.assemblies:
        in_degrees[assembly.idx] = get_indegrees(conn_mat, assembly.gids, pre_gids)
        ind_ctrl["n"][assembly.idx] = get_indegrees(conn_mat, np.random.choice(pre_gids, len(assembly.gids),
                                                                               replace=False), pre_gids)
        ind_ctrl["depths"][assembly.idx] = get_indegrees(conn_mat,
                                           assembly.random_numerical_control(pre_nrn, "[PH]y").gids, pre_gids)
        ind_ctrl["mtypes"][assembly.idx] = get_indegrees(conn_mat,
                                           assembly.random_categorical_control(pre_nrn, "mtype").gids, pre_gids)
    fig_name = os.path.join(config.fig_path, "%s_in_degrees_%s.png" % (plot_txt, seed))
    plot_in_degrees(in_degrees, ind_ctrl, fig_name, xlabel="%s in degree" % plot_txt)


if __name__ == "__main__":
    config = Config("../configs/visual_contrast.yaml")
    get_mtype_indegree(config, {"$regex": "L(23|4|5|6)_MC"}, "PC-MC")
    get_mtype_indegree(config, {"$regex": "L(23|4|5|6)_(LBC|NBC|CHC)"}, "PC-PVBC")

