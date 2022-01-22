"""
Main run function for finding synapse cluster on assembly neurons
last modified: András Ecker 01.2022
"""

import os
import logging
from tqdm import tqdm
import numpy as np

from assemblyfire.config import Config
from assemblyfire.utils import load_assemblies_from_h5, get_sim_path, get_bluepy_circuit, save_syn_clusters
from assemblyfire.topology import AssemblyTopology
from assemblyfire.clustering import cluster_synapses

L = logging.getLogger("assemblyfire")


def run(config_path, debug):
    """
    Loads in asssemblies and connectivity matrix from saved h5 file, and for each assembly
    finds the most innervated neurons, looks for synapse clusters and saved to pickle files
    :param config_path: str - path to project config file
    :param debug: bool - to save figures for visual inspection
    """

    config = Config(config_path)
    L.info(" Load in assemblies and connectivity matrix from %s" % config.h5f_name)
    assembly_grp_dict, _ = load_assemblies_from_h5(config.h5f_name, config.h5_prefix_assemblies)
    conn_mat = AssemblyTopology.from_h5(config.h5f_name,
                                        prefix=config.h5_prefix_connectivity, group_name="full_matrix")

    L.info(" Detecting synapse clusters and saving them to files")
    c = get_bluepy_circuit(get_sim_path(config.root_path).iloc[0])
    for seed, assembly_grp in tqdm(assembly_grp_dict.items(), desc="Iterating over seeds"):
        for assembly in tqdm(assembly_grp.assemblies, desc="%s syn. clusters" % seed, leave=False):
            fig_dir = os.path.join(config.fig_path, "%s_debug" % seed) if debug else None
            sort_idx = np.argsort(conn_mat.degree(assembly, kind="in"))[::-1]  # sort by in-degree
            post_gids = assembly.gids[sort_idx[:config.syn_clustering_n_neurons_sample]]
            cluster_df = cluster_synapses(c, post_gids, assembly, config.syn_clustering_target_range,
                                          config.syn_clustering_min_nsyns, fig_dir=fig_dir)
            save_syn_clusters(config.root_path, assembly.idx, cluster_df)

