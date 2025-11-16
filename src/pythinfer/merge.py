"""Merge RDF graphs from config, preserving named graph URIs for each input file."""

from rdflib import ConjunctiveGraph

from .inout import Project


def merge_graphs(
    cfg: Project,
) -> tuple[ConjunctiveGraph, ConjunctiveGraph, ConjunctiveGraph]:
    """Merge graphs, preserving named graphs for each input and keeping graph types separate.

    Returns a tuple of (data, vocabs_internal, vocabs_external) conjuctive graphs.
    """
    external = ConjunctiveGraph()
    internal = ConjunctiveGraph()
    data = ConjunctiveGraph()
    for src in cfg.paths_vocab_ext:
        external.parse(src, format="turtle", publicID=str(src))
    for src in cfg.paths_vocab_int:
        internal.parse(src, format="turtle", publicID=str(src))
    for src in cfg.paths_data:
        data.parse(src, format="turtle", publicID=str(src))
    return data, internal, external
