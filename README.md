# pythinfer - Python Logical Inference

*Pronounced 'python fur'.*

This is a package to perform OWL-based inference, provided by external packages, to an RDF graph.

Point this at a selection of RDF files and it will merge them, run inference over them, and export the results. The results are the original statements together with the *useful* set of inferences (see below under `Inference` for what 'useful' means here).

In the inference, a distinction is made between 'external' and 'internal' files. See below.

The backends that should be supported are:

1. rdflib
1. pyoxigraph
1. jena
1. rdf4j?

## 'Project'

A 'Project' is the specification of which RDF files to process and configuration of how to process them, along with some metadata like a name.

Because we will likely have several files and they will be of different types, it is easiest to specify these in a configuration file (YAML or similar) instead of requiring everything on the command line.

The main function or CLI can then be pointed at the project file to easily switch between projects. This also allows the same sets and subsets of inputs to be combined in different ways with configuration.

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

NB: the default `base_folder` is the folder in which the Project configuration file resides.

### Project Discovery

If a project file is not explicitly specified, `pythinfer` should operate like `git` or `uv` - it should search for a `pythinfer.yaml` file in the current directory, and then in parent directories up to a limit.

The limit on ancestors should be:
1. don't traverse below `$HOME` if that is in the ancestral line
1. don't go beyond 10 folders
1. don't traverse across file systems

If no project file found, it should do a search for RDF files in current directory.

There should also be a command to generate a new project file, based on the above search. An option should be available to automatically output a project file with the above search, best likely default-true.

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

## Querying

A simple helper command should allow easily specifying a query, or queries, and these should be executed against the latest full inferred graph.

In principle, the tool could also take care of dependency management so that any change in an input file is automatically re-merged and inferred before a query...

## Data Structures

### DatasetView

Intended to give a restricted (filtered) view on a Dataset by only providing access to explicitly selected graphs, enabling easy handling of a subset of graphs without copying data to new graphs.

Specifications:
1. A DatasetView may be read/write or readonly.
1. Graphs MUST be explicitly included to be visible, otherwise they are excluded (and invisible).
1. Attempted access to excluded graphs MUST raise a PermissionError.
1. Default graph MUST therefore be excluded if the underlying Dataset has `default_union` set (because otherwise this would counterintuitively render triples from excluded graphs visible to the view).
1. A DatasetView SHOULD otherwise operate in exactly the same way as the underlying Dataset.

#### Inclusion and Exclusion of Graphs

`rdflib`'s handling of access, addition, and deletion of named graphs has some unintuitive nuance. See [this issue](https://github.com/robertmuil/rdflib/issues/18) for the most relevant example.

For the View, we want to adopt as little difference to APIs and expectations as possible, which unfortunately means taking on the unintuitive behaviours.

So, there are *no* methods for including or excluding a graph once a view is created, because the behaviour of such methods would be very difficult to define. If the included graphs needs to be changed, a new DatasetView should simply be created, which is light-weight because no copying is involved.

## Next Steps

1. implement pattern support for input files
1. implement categoriseddataset as a subclass not a container
1. implement search for input if no project files found
1. implement project creation command
1. allow Python-coded inference rules (e.g. for path-traversal or network analytics)
1. allow SPARQL CONSTRUCTs as rules for inference
1. implement base_folder support - perhaps more generally support for specification of any folder variables...
1. consider using a proper config language like dhal(?) instead of yaml
1. consider simplifying categories of input to just be 'external' and 'internal' - do we really need to distinguish between internal vocabs and data?
1. add query command



