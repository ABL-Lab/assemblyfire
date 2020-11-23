# -*- coding: utf-8 -*-
"""
CLI to detect and analyse cell assemblies
 * `assemblyfire find-assemblies` config_path: detect assemblies in spiking data
 * `assemblyfire analyse-assemblies`: TODO
last modified: András Ecker 11.2020
"""

import click
import logging

L = logging.getLogger("assemblyfire")


def set_verbose(logger, verbose):
    """Set the verbose level for the CLI"""
    logger.setLevel((logging.WARNING, logging.INFO, logging.DEBUG)[min(verbose, 2)])

'''
@click.group()
@click.option('-v', '--verbose', count=True)
def cli(verbose):
    """CLI entry point."""
    set_verbose(L, verbose)
'''

@click.group()
def cli():
    """CLI entry point."""
    L.setLevel(logging.INFO)


@cli.command()
@click.argument("config_path", required=True)
def find_assemblies(config_path):
    """CLI for `find_assemblies.py/run()`"""
    from assemblyfire.find_assemblies import run
    run(config_path)
