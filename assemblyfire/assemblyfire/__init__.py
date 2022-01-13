"""assemblyfire"""

from assemblyfire.version import __version__
from assemblyfire.spikes import SpikeMatrixGroup, spikes2mat, sign_rate_std, spikes_to_h5
from assemblyfire.assemblies import Assembly, AssemblyGroup, ConsensusAssembly
# from assemblyfire.topology import NetworkAssembly  # TODO: fix this...
from assemblyfire.clustering import cluster_sim_mat, cluster_spikes, detect_assemblies, cluster_assemblies
from assemblyfire import utils
from assemblyfire import plots

