# -*- coding: utf-8 -*-
"""
CLI to detect and analyse cell assemblies
 * `assemblyfire find-assemblies` config_path: detect assemblies in spiking data
 * `assemblyfire consensus config_path`: create consensus assemblies from assemblies across seeds
 * `assemblyfire conn-mat`: loads in connectivity matrix
 * `assemblyfire single-cell config_path`: gets single cell features from simulations
last modified: Thomas Delemontex, András Ecker 11.2020
"""

import click
import logging

logging.basicConfig(level=logging.INFO)
L = logging.getLogger("assemblyfire")


def set_verbose(logger, verbose):
    """Set the verbose level for the CLI"""
    logger.setLevel((logging.WARNING, logging.INFO, logging.DEBUG)[min(verbose, 2)])


@click.group()
@click.option('-v', '--verbose', count=True)
def cli(verbose):
    """CLI entry point."""
    set_verbose(L, verbose)


@cli.command()
@click.argument("config_path", required=True)
def find_assemblies(config_path):
    """CLI for `find_assemblies.py/run()`"""
    from assemblyfire.find_assemblies import run
    run(config_path)
    

@cli.command()
@click.argument("config_path", required=True)
def consensus(config_path):
    """CLI for `find_consensus_assemblies.py/run()`"""
    from assemblyfire.find_consensus_assemblies import run
    run(config_path)


@cli.command()
@click.argument("config_path", required=True)
def conn_mat(config_path):
    """CLI for `get_connectivity_matrix.py/run()`"""
    from assemblyfire.get_connectivity_matrix import run
    run(config_path)


@cli.command()
@click.argument("config_path", required=True)
def single_cell(config_path):
    """CLI for `get_single_cell_features.py/run()`"""
    from assemblyfire.get_single_cell_features import run
    run(config_path)


@cli.command()
@click.argument("config_path", required=True)
@click.argument("prefix", required=True)
def clean_h5(config_path, prefix):
    """Removes data under the given `prefix` in the HDF5 file"""
    import yaml
    import h5py
    with open(config_path, "r") as f:
        config = yaml.load(f, Loader=yaml.SafeLoader)
    assert prefix in config["h5_out"]["prefixes"], "Prefix name doesn't exist in the config."
    h5f = h5py.File(config["h5_out"]["file_name"], "a")
    del h5f[config["h5_out"]["prefixes"][prefix]]
