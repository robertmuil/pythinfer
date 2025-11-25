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

### Project Configuration

OLD:

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

NEW:

```yaml
name: (optional)
base_folder: <all relative paths are resolved against this> (optional - defaults to folder in which the Project configuration file resides.)
data:
    internal:
        - <pattern>: <a pattern specifying a specific or set of files>
    external:
        - <pattern>: <a pattern specifying a specific or set of external files>
output:
    folder: <a path to the folder in which to put the output> (defaults to `<base_folder>/derived`)
```

#### External vs Internal

External files are those that are not maintained by the user of the library, and whose axioms can generally be assumed to hold true for any application. They are used to provide inference rules, but are not part of the data being modelled, and they are not generally needed in the output.

Examples are OWL, RDFS, SKOS, and other standard vocabularies.

Synonyms for 'external' here could be 'transient' or 'reference' or 'catalyst'.

Need better term than 'internal' because it can be data (incl. vocabs and models) that are maintained outside of the project folder itself, but are desired to be part of the output. Perhaps 'local'.

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

### Inference Process

Steps:

1. **Load and merge** all input data into a triplestore
    - Maintain provenance of data by named graph
    - Maintain list of which named graphs are 'external'
    - output:        `merged`
    - consequence:   `current = merged`
2. **Generate external inferences** by running RDFS/OWL-RL engine over 'external' input data[^1]
    - output:        `external_owl_inferences`
3. **Generate full inferences** by running RDFS/OWL-RL inference over all data so far[^1]
    - output:        `full_owl_inferences`
    - consequence:   `current += full_owl_inferences`
4. **Run heuristics**[^2] over all data
    - output:        `heuristic_results`
    - consequence:   `current += heuristic_results`
5. **Repeat steps 3 through 4** until no new triples are generated, or limit reached
6. **Subtract external data and inferences** from the current graph
    - consequence:   `current -= external_data + external_owl_inferences`
7. Subtract all 'unwanted' inferences from result[^3]
    - consequence:   `final = current - unwanted_inferences`

[^1]: inference is backend dependent, and will include the removal of *invalid* triples that may result, e.g. from `owlrl`
[^2]: See below for heuristics.
[^3]: unwanted inferences are those that are semantically valid but not useful, see below

### Backends

#### `rdflib` and `owlrl`

In rdflib, the `owlrl` package should be used.

This package has some foibles. For instance, it generates a slew of unnecessary triples. The easiest way to remove these is to first run inference over all 'external' vocabularies, then combine with the user-provided vocabularies and data, run inference, and then remove all the original inferences from the 'external' vocabularies from the final result. The external vocabularies themselves can also be removed, depending on application.

Unwanted inferences are generated even when executed over an empty graph.

#### `pyoxigraph`

No experience with this yet.

#### Jena (`riot` etc.)

Because Jena provides a reference implementation, it might be useful to be able to call out to the Jena suite of command line utilities (like `riot`) for manipulation of the graphs (including inference).

#### Heuristics (SPARQL, Python, etc.)

Some inferences are difficult or impossible to express in OWL-RL. This will especially be the case for very project-specific inferences which are trivial to express procedurally but complicated in a logical declaration.

Therefore we want to support specification of 'heuristics' in other formalisms, like SPARQL CONSTRUCT queries and Python functions.

The order of application of these heuristics may matter - for instance, a SPARQL CONSTRUCT may create triples that are then used by a Python heuristic, or the former may require the full type hierarchy to be explicit from OWL-RL inference.

Thus, we apply heuristics and OWL-RL inference in alternating steps until no new triples are generated.

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

#### Adding and removing content

Adding a new graph is not possible through the View unless it was in the list of included graphs at construction, because it only allows accessing included graphs. If an identifier is in the original included list, but has no corresponding triples in the underlying triplestore, this is allowed, and subsequent addition of a triple against that graph identifier would defacto essentially be the 'addition' of a graph to the store.

Removing a graph likewise performs exactly as if performed on the underlying Dataset, unless the graph's identifier is not in the inclusion list, in which case it generates a `PermissionError`. In either case, the graph remains in the inclusion list.

Adding and removing triples is possible (unless the View is set to read-only, which may not be implemented) as long as the triples are added to a graph in the inclusion list.

Adding or removing a triple without specifying the graph would go to the default graph and the same check applies: if the default graph is in the inclusion list, this is allowed, otherwise it will raise a `PermissionError`.

This is all following the principle of altering the API of `Dataset` as little as possible.

## Next Steps

1. implement pattern support for input files
1. implement search for input if no project files found
1. implement project creation command
1. allow Python-coded inference rules (e.g. for path-traversal or network analytics)
1. allow SPARQL CONSTRUCTs as rules for inference
1. implement base_folder support - perhaps more generally support for specification of any folder variables...
1. consider using a proper config language like dhal(?) instead of yaml
1. add query command
