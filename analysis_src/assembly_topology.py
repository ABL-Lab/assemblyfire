"""
In degrees, simplex counts, pot/dep ratios, and membership probabilities of assemblies
last modified: András Ecker 10.2022
"""

import os
from tqdm import tqdm
import numpy as np
import pandas as pd

from assemblyfire.config import Config
import assemblyfire.utils as utils
import assemblyfire.topology as topology
import assemblyfire.plots as plots



def assembly_efficacy(config):
    """Loads in assemblies and plots synapses initialized at depressed (rho=0) and potentiated (rho=1) states"""

    assembly_grp_dict, _ = utils.load_assemblies_from_h5(config.h5f_name, config.h5_prefix_assemblies)
    c = utils.get_bluepy_circuit(utils.get_sim_path(config.root_path).iloc[0])
    rhos = utils.get_rho0s(c, config.target)  # get all rhos in one go and then index them as needed

    for seed, assembly_grp in tqdm(assembly_grp_dict.items(), desc="Getting efficacies"):
        efficacies = {assembly.idx[0]: rhos.loc[rhos["pre_gid"].isin(assembly.gids)
                                                & rhos["post_gid"].isin(assembly.gids), "rho"].value_counts()
                      for assembly in assembly_grp.assemblies}
        fig_name = os.path.join(config.fig_path, "efficacy_%s.png" % seed)
        plots.plot_efficacy(efficacies, fig_name)


def assembly_in_degree(config):
    """Loads in assemblies and plots in degrees within the assemblies and in their control models (seed by seed)"""

    conn_mat = AssemblyTopology.from_h5(config.h5f_name,
                                        prefix=config.h5_prefix_connectivity, group_name="full_matrix")
    assembly_grp_dict, _ = utils.load_assemblies_from_h5(config.h5f_name, config.h5_prefix_assemblies)

    in_degrees, in_degrees_control = in_degree_assemblies(assembly_grp_dict, conn_mat)
    for seed, in_degree in in_degrees.items():
        fig_name = os.path.join(config.fig_path, "in_degrees_%s.png" % seed)
        plots.plot_in_degrees(in_degree, in_degrees_control[seed], fig_name)


def assembly_simplex_counts(config):
    """Loads in assemblies and plots simplex counts in assemblies and control models (seed by seed)"""

    conn_mat = AssemblyTopology.from_h5(config.h5f_name,
                                        prefix=config.h5_prefix_connectivity, group_name="full_matrix")
    assembly_grp_dict, _ = utils.load_assemblies_from_h5(config.h5f_name, config.h5_prefix_assemblies)

    simplex_counts, simplex_counts_control = simplex_counts_assemblies(assembly_grp_dict, conn_mat)
    for seed, simplices in simplex_counts.items():
        fig_name = os.path.join(config.fig_path, "simplex_counts_%s.png" % seed)
        plots.plot_simplex_counts(simplices, simplex_counts_control[seed], fig_name)


def _mi_implementation(degree_counts, degree_p):
    """
    Analyzes how much of the uncertainty of assembly membership is explained away when one considers the strengths
    of innervation from a given pre-synaptic target (in terms of in-degree).
    :param degree_counts: The number of neurons in the simulation that have a given degree. One entry per degree-bin.
    :param degree_p: The probability that neurons with a given degree are members of the assembly in question.
                     (Must have same length as degree_counts.) Note: Yes, for this analysis the actual _value_
                     of a degree-bin (which min/max degree does it represent?) is irrelevant. - Michael W.R.
    :return: membership_entropy: The prior entropy of assembly membership.
    :return: posterior_entropy: The posterior entropy of assembly membership conditional on the innervation degree.
    """

    def entropy(p):
        return -np.log2(p) * p - np.log2(1 - p) * (1 - p)

    def entropy_vec(p_vec):
        return np.nansum(np.vstack([-np.log2(p_vec) * p_vec, -np.log2(1 - p_vec) * (1 - p_vec)]), axis=0)

    degree_counts, degree_p = np.array(degree_counts), np.array(degree_p)
    overall_p = (degree_counts * degree_p).sum() / degree_counts.sum()
    membership_entropy = entropy(overall_p)
    posterior_entropy = (entropy_vec(degree_p) * degree_counts).sum() / degree_counts.sum()
    return membership_entropy, posterior_entropy


def _sign_of_correlation(degree_vals, degree_p):
    """
    Analyzes whether the strength of innervation from a given pre-synaptic target (in terms of in-degree) is rather
    increasing (positive sign) or decreasing (negative sign) the probability that the innervated neuron is member of
    an assembly.
    :param degree_vals: The possible values of degrees for the innervated neurons. e.g. the centers of degree-bins.
    :param degree_p: The probability that neurons with a given degree are members of the assembly in question.
                     (Must have same length as degree_counts.)
    :return: sign: -1 if stronger innervation decreases probability of membership; 1 if it rather increases it
    """
    degree_vals, degree_p = np.array(degree_vals), np.array(degree_p)
    idx = np.argsort(degree_vals)
    return np.sign(np.polyfit(degree_vals[idx], degree_p[idx], 1)[0])


def frac_entropy_explained_by_indegree(config, min_samples=100):
    """Loads in assemblies and for each of them plots the probabilities of assembly membership
    vs. in degree (from the assembly neurons) as well as the (relative) loss in entropy. i.e. How much percent
    of the uncertainty (in assembly membership) can be explained by pure structural innervation"""

    conn_mat = AssemblyTopology.from_h5(config.h5f_name,
                                        prefix=config.h5_prefix_connectivity, group_name="full_matrix")
    gids = conn_mat.gids
    assembly_grp_dict, _ = utils.load_assemblies_from_h5(config.h5f_name, config.h5_prefix_assemblies)

    assembly_indegrees_dict = {}
    for seed, assembly_grp in assembly_grp_dict.items():
        assembly_indegrees = {assembly.idx[0]: conn_mat.degree(assembly.gids, gids)
                              for assembly in assembly_grp.assemblies}
        assembly_indegrees_dict[seed] = pd.DataFrame(assembly_indegrees, index=gids)
        binned_gids, bin_centers = _bin_gids_by_innervation(assembly_indegrees, gids, min_samples)

        chance_levels = {}
        bin_centers_plot = {pre_assembly: {} for pre_assembly in list(binned_gids.keys())}
        assembly_probs = {pre_assembly: {} for pre_assembly in list(binned_gids.keys())}
        assembly_mi = {pre_assembly: {} for pre_assembly in list(binned_gids.keys())}
        for assembly in assembly_grp.assemblies:
            assembly_id = assembly.idx[0]
            idx = np.in1d(gids, assembly.gids, assume_unique=True)
            chance_levels[assembly_id] = idx.sum() / len(idx)
            for pre_assembly, binned_gids_tmp in binned_gids.items():
                probs, counts, vals = [], [], []
                for bin_center in bin_centers[pre_assembly]:
                    idx = np.in1d(binned_gids_tmp[bin_center], assembly.gids, assume_unique=True)
                    probs.append(idx.sum() / len(idx))
                    counts.append(len(binned_gids_tmp[bin_center]))
                    vals.append(bin_center)
                bin_centers_plot[pre_assembly][assembly_id] = bin_centers[pre_assembly]
                assembly_probs[pre_assembly][assembly_id] = np.array(probs)
                me, pe = _mi_implementation(counts, probs)
                assembly_mi[pre_assembly][assembly_id] = _sign_of_correlation(vals, probs) * (1.0 - pe / me)

        fig_name = os.path.join(config.fig_path, "assembly_prob_from_indegree_%s.png" % seed)
        palette = {assembly.idx[0]: "pre_assembly_color" for assembly in assembly_grp.assemblies}
        plots.plot_assembly_prob_from(bin_centers_plot, assembly_probs, chance_levels,
                                      "In degree", palette, fig_name)
        fig_name = os.path.join(config.fig_path, "frac_entropy_explained_by_recurrent_innervation_%s.png" % seed)
        plots.plot_frac_entropy_explained_by(pd.DataFrame(assembly_mi).transpose(), "Innervation by assembly", fig_name)

    return assembly_indegrees_dict


def _nnd_df_to_dict(nnd_df):
    """Converts DataFrame from `clustering.syn_nearest_neighbour_distances()` to the dict format
    which is compatible with the `_bin_gids_by_innervation()` helper functions above"""
    gids = nnd_df.index.to_numpy()
    assembly_idx = nnd_df.columns.to_numpy()
    return {assembly_id: nnd_df[assembly_id].to_numpy() for assembly_id in assembly_idx}, gids


def frac_entropy_explained_by_syn_nnd(config, min_samples=100):
    """Loads in assemblies and for each (sub)target neurons calculates the (normalized) nearest neighbour distance
    for assembly synapses (which is meant to be a parameter free measure of synapse clustering) and plots the prob.
    of assembly membership vs. this measure"""
    from assemblyfire.clustering import syn_nearest_neighbour_distances

    assembly_grp_dict, _ = utils.load_assemblies_from_h5(config.h5f_name, config.h5_prefix_assemblies)
    c = utils.get_bluepy_circuit(utils.get_sim_path(config.root_path).iloc[0])
    loc_df = utils.get_loc_df(config.syn_clustering_lookup_df_pklfname, c, config.target, config.syn_clustering_target)
    mtypes = utils.get_mtypes(c, utils.get_gids(c, config.target)).reset_index()
    mtypes.rename(columns={"index": "gid"}, inplace=True)

    assembly_nnds_dict = {}
    for seed, assembly_grp in assembly_grp_dict.items():
        ctrl_assembly_grp = assembly_grp.random_categorical_controls(mtypes, "mtype")
        assembly_nnds, ctrl_nnds = syn_nearest_neighbour_distances(loc_df, assembly_grp, ctrl_assembly_grp)
        assembly_nnds_dict[seed] = assembly_nnds
        binned_gids, bin_centers = _bin_gids_by_innervation(*_nnd_df_to_dict(assembly_nnds), min_samples)

        chance_levels = {}
        bin_centers_plot = {pre_assembly: {} for pre_assembly in list(binned_gids.keys())}
        assembly_probs = {pre_assembly: {} for pre_assembly in list(binned_gids.keys())}
        assembly_mi = {pre_assembly: {} for pre_assembly in list(binned_gids.keys())}
        for assembly in assembly_grp.assemblies:
            assembly_id = assembly.idx[0]
            idx = np.in1d(assembly_nnds[assembly_id].to_numpy(), assembly.gids, assume_unique=True)
            chance_levels[assembly_id] = idx.sum() / len(idx)
            for pre_assembly, binned_gids_tmp in binned_gids.items():
                probs, counts, vals = [], [], []
                for bin_center in bin_centers[pre_assembly]:
                    idx = np.in1d(binned_gids_tmp[bin_center], assembly.gids, assume_unique=True)
                    probs.append(idx.sum() / len(idx))
                    counts.append(len(binned_gids_tmp[bin_center]))
                    vals.append(bin_center)
                bin_centers_plot[pre_assembly][assembly_id] = bin_centers[pre_assembly]
                assembly_probs[pre_assembly][assembly_id] = np.array(probs)
                me, pe = _mi_implementation(counts, probs)
                assembly_mi[pre_assembly][assembly_id] = _sign_of_correlation(vals, probs) * (1.0 - pe / me)

        fig_name = os.path.join(config.fig_path, "assembly_prob_from_syn_nearest_neighbour_%s.png" % seed)
        palette = {assembly.idx[0]: "pre_assembly_color" for assembly in assembly_grp.assemblies}
        plots.plot_assembly_prob_from(bin_centers_plot, assembly_probs, chance_levels,
                                      "Synapse nearest neighbour distance", palette, fig_name)
        fig_name = os.path.join(config.fig_path, "frac_entropy_explained_by_syn_nearest_neighbour_%s.png" % seed)
        plots.plot_frac_entropy_explained_by(pd.DataFrame(assembly_mi).transpose(),
                                             "Synapse nearest neighbour from assembly", fig_name)

    return assembly_nnds_dict


def assembly_prob_from_indegree_and_syn_nnd(config, assembly_indegrees_dict, assembly_nnds_dict,
                                            palette, min_samples=100):
    """Combines previous results and weights indegrees with synapse neighbour distances
    (and then predicts assembly membership from that for all assemblies)"""

    assembly_grp_dict, _ = utils.load_assemblies_from_h5(config.h5f_name, config.h5_prefix_assemblies)
    keys = list(palette.keys())

    for seed, assembly_grp in assembly_grp_dict.items():
        assembly_indegrees, assembly_nnds = assembly_indegrees_dict[seed], assembly_nnds_dict[seed]
        chance_levels = {}
        assembly_probs = {key: {} for key in keys}
        bin_centers_dict = {key: {} for key in keys}
        for assembly in assembly_grp.assemblies:
            assembly_id = assembly.idx[0]
            binned_assembly_nnds = pd.qcut(assembly_nnds.loc[assembly_nnds[assembly_id] > 0, assembly_id],
                                           len(keys), labels=keys)
            idx = np.in1d(binned_assembly_nnds.index.to_numpy(), assembly.gids, assume_unique=True)
            chance_levels[assembly_id] = idx.sum() / len(idx)
            for key in keys:
                gids = binned_assembly_nnds.loc[binned_assembly_nnds == key].index.to_numpy()
                key_assembly_indegrees = assembly_indegrees.loc[gids, assembly_id]
                bin_edges, bin_centers = utils.determine_bins(*np.unique(key_assembly_indegrees.to_numpy(),
                                                                         return_counts=True), min_samples)
                bin_centers_dict[key][assembly_id] = bin_centers
                bin_idx = np.digitize(key_assembly_indegrees.to_numpy(), bin_edges, right=True)
                gids_tmp, probs = key_assembly_indegrees.index.to_numpy(), []
                for i, center in enumerate(bin_centers):
                    idx = np.in1d(gids_tmp[bin_idx == i + 1], assembly.gids, assume_unique=True)
                    probs.append(idx.sum() / len(idx))
                assembly_probs[key][assembly_id] = np.array(probs)

        fig_name = os.path.join(config.fig_path, "assembly_prob_from_indegree_syn_nnd_%s.png" % seed)
        plots.plot_assembly_prob_from(bin_centers_dict, assembly_probs, chance_levels,
                                      "Innervation by assembly (weighted by synapse nnd.)", palette, fig_name)


def assembly_prob_from_sinks(config, palette, min_samples=100):
    """Loads in assemblies and plots generalized in degrees (sinks of high dim. simplices) within the assemblies
    (seed by seed). Simplices are found in a way that all non-sink neurons are guaranteed to be within the assembly"""

    conn_mat = AssemblyTopology.from_h5(config.h5f_name,
                                        prefix=config.h5_prefix_connectivity, group_name="full_matrix")
    assembly_grp_dict, _ = utils.load_assemblies_from_h5(config.h5f_name, config.h5_prefix_assemblies)
    gids = conn_mat.gids
    dims = list(palette.keys())

    for seed, assembly_grp in assembly_grp_dict.items():
        chance_levels, bin_centers_dict, assembly_probs = {}, {dim: {} for dim in dims}, {dim: {} for dim in dims}
        for assembly in tqdm(assembly_grp.assemblies, desc="Iterating over assemblies"):
            idx = np.in1d(gids, assembly.gids, assume_unique=True)
            chance_levels[assembly.idx[0]] = idx.sum() / len(idx)
            simplex_list = conn_mat.simplex_list(assembly.gids, gids)
            for dim in dims:
                sink_counts, _ = np.histogram(simplex_list[dim][:, -1], np.arange(len(gids) + 1))
                bin_edges, bin_centers = utils.determine_bins(*np.unique(sink_counts, return_counts=True), min_samples)
                bin_edges, bin_centers = np.insert(bin_edges, 0, -1), np.insert(bin_centers, 0, 0)
                bin_centers_dict[dim][assembly.idx[0]] = bin_centers
                bin_idx = np.digitize(sink_counts, bin_edges, right=True)
                probs = []
                for i, center in enumerate(bin_centers):
                    idx = np.in1d(gids[bin_idx == i + 1], assembly.gids, assume_unique=True)
                    probs.append(idx.sum() / len(idx))
                assembly_probs[dim][assembly.idx[0]] = np.array(probs)

        fig_name = os.path.join(config.fig_path, "assembly_prob_from_simplex_dim_%s.png" % seed)
        plots.plot_assembly_prob_from(bin_centers_dict, assembly_probs, chance_levels,
                                      "Generalized in degree (#simplex sinks)", palette, fig_name, True)


def _get_spiking_proj_gids(config, sim_config):
    """Loads grouped (to patterns + non-specific) TC gids
    (Could be done easier with adding stuff to the yaml config... but whatever)"""
    tc_spikes = utils.get_grouped_tc_spikes(config.pattern_gids_fname, sim_config, config.t_start, config.t_end)
    _, patterns = utils.get_stimulus_stream(config.input_patterns_fname, config.t_start, config.t_end)
    pattern_names = np.unique(patterns)
    projf_names = list(utils.get_projf_names(sim_config).keys())
    assert len(projf_names) <= 2, "The code assumes max 2 projections, one pattern specific and one non-specific"
    ns_projf_name = np.setdiff1d(projf_names, [config.patterns_projection_name])[0]
    pattern_gids, ns_gids = {}, []
    for name, data in tc_spikes.items():
        if name in pattern_names:
            pattern_gids[name] = np.unique(data["spiking_gids"])
        else:
            ns_gids.extend(np.unique(data["spiking_gids"]))
    all_pattern_gids = []
    for pattern_name, gids in pattern_gids.items():
        all_pattern_gids.extend(gids)
    return {config.patterns_projection_name: np.unique(all_pattern_gids), ns_projf_name: np.unique(ns_gids)}, pattern_gids


def get_proj_innervation(config):
    """Looks up how many projection fibers, and pattern fibers innervate the neurons"""
    from conntility.circuit_models import circuit_connection_matrix

    sim = utils.get_bluepy_simulation(utils.get_sim_path(config.root_path).iloc[0])
    proj_gids, pattern_gids = _get_spiking_proj_gids(config, sim.config)
    c = sim.circuit
    post_gids = utils.get_gids(c, config.target)
    proj_indegrees, pattern_indegrees, mutual_innervation_matrices = {}, {}, {}
    for proj, pre_gids in proj_gids.items():
        # get (sparse) connectivity matrix between the input fibers and neurons in the circuit
        input_conn_mat = circuit_connection_matrix(c, proj, pre_gids, post_gids).tocsr()
        mutual_innervation_matrices[proj] = input_conn_mat.transpose() * input_conn_mat
        proj_indegrees[proj] = np.array(input_conn_mat.sum(axis=0)).flatten()
        if proj == config.patterns_projection_name:
            # for each pattern get how many pattern fibers innervate the neurons
            for pattern_name, gids in pattern_gids.items():
                pattern_idx = np.in1d(pre_gids, gids, assume_unique=True)
                pattern_indegrees[pattern_name] = np.array(input_conn_mat[pattern_idx].sum(axis=0)).flatten()

    return proj_indegrees, pattern_indegrees, mutual_innervation_matrices, post_gids


def assembly_prob_mi_from_patterns(assembly_grp_dict, pattern_indegrees, gids, fig_path,
                                   n_bins=21, bin_min_n=10, sign_th=2):
    """Plots assembly probabilities and (relative) fraction of entropy explained from pattern indegrees"""
    binned_gids, bin_centers, bin_idx = topology.bin_gids_by_innervation(pattern_indegrees, gids, n_bins)
    for seed, assembly_grp in assembly_grp_dict.items():
        plot_args = topolgy.assembly_membership_probability(gids, assembly_grp, binned_gids, bin_centers, bin_min_n)
        fig_name = os.path.join(fig_path, "assembly_prob_from_patterns_%s.png" % seed)
        plots.plot_assembly_prob_from(*plot_args, "In degree from patterns", "patterns", fig_name)

        mi = topology.assembly_rel_frac_entropy_explained(gids, assembly_grp, bin_centers, bin_idx, seed, sign_th)
        fig_name = os.path.join(fig_path, "frac_entropy_explained_by_patterns_%s.png" % seed)
        plots.plot_frac_entropy_explained_by(mi, "Innervation by pattern", fig_name)


if __name__ == "__main__":
    config = Config("../configs/v7_10seeds_np.yaml")
    assembly_grp_dict, _ = utils.load_assemblies_from_h5(config.h5f_name, config.h5_prefix_assemblies)

    # assembly_efficacy(config)
    # assembly_in_degree(config)
    # assembly_simplex_counts(config)
    # assembly_indegrees = frac_entropy_explained_by_indegree(config)
    # assembly_nnds = frac_entropy_explained_by_syn_nnd(config)
    # assembly_prob_from_indegree_and_syn_nnd(config, assembly_indegrees, assembly_nnds,
    #                                         {"below avg.": "assembly_color", "avg.": "gray", "above avg.": "black"})
    # assembly_prob_from_sinks(config, {2: "lightgray", 3: "gray", 4: "black", 5: "assembly_color"})

    _, pattern_indegrees, mutual_innervation_matrices, gids = get_proj_innervation(config)
    assembly_prob_mi_from_patterns(assembly_grp_dict, pattern_indegrees, gids, config.fig_path)

