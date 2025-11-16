# pythinfer - Python Logical Inference

Summary: point this at a selection of RDF files and it will merge them, run inference over them, and output/export the results. The results are the original statements together with the *useful* set of inferences (see below under Inference for what 'useful' means here).

Package to perform various forms of inference, provided by external packages, to an RDF graph.

This can merge multiple graphs (i.e. graphs parsed from multiple files).

The backends that should be supported are:

1. rdflib
1. pyoxigraph
1. jena
1. rdf4j?

## 'Project'

We define a 'Project' simply as the full collection of RDF input, along with any necessary metadata, that will be processed.

Because we will likely have several files and of different types, it is likely easiest to specify these in a config file (YAML or similar) instead of requiring everything on the command line.

The main function / CLI can then be pointed at the project file to easily switch between projects. This also allows the same sets and subsets of inputs to be combined in different ways with configuration.

### Proposed Project Configuration

```yaml
- name: (optional)
- base_folder: <all relative paths are resolved against this> (optional)
- external_vocabs: a list of patterns specifying external ontologies
    - <pattern>: a pattern specifying a specific or set of external files
- internal_vocabs: a list of patterns specifying internal ontologies
    - <pattern>: as above
- data: a list of patterns specifying data files
    - <pattern>: as above
- output: a path to the folder in which to put the output (defaults to parent of 1st data file found)
```

Q: What is the default `base_folder`? Is it the src folder or the main pythinfer project folder? The latter makes most sense...

## Merging

Merging of multiple graphs should preserve the source, ideally using the named graph of a quad.

Merging should also distinguish 3 different types of input:

1. 'external' vocabularies - things like OWL, SKOS, RDFS, which are introduced for inference purposes, but are not maintained by the person using the library, and the axioms of which can generally be assumed to exist for any application.
1. 'internal' vocabularies - ontologies being developed, vocabularies that are part of the 

## Inference

By default an efficient OWL rule subset should be used, like OWL-RL.

### 'Useful' inferences

Many inferences are so obvious and/or banal that they are not useful. For instance, every instance could be considered to be the `owl:sameAs` itself. This is semantically valid but useless to express as an explicit triple.

### `rdflib` and `owlrl`

In rdflib, the `owlrl` package should be used.

This package has some foibles. For instance, it generates a slew of unnecessary triples. The easiest way to remove these is to first run inference over all 'external' vocabularies, then combine with the user-provided vocabularies and data, run inference, and then remove all the original inferences from the 'external' vocabularies from the final result. The external vocabularies themselves can also be removed, depending on application.

### `pyoxigraph`

No experience with this yet.

### Jena (`riot` etc.)

Because Jena provides a reference implementation, it might be useful to be able to call out to the Jena suite of command line utilities (like `riot`) for manipulation of the graphs (including inference).
