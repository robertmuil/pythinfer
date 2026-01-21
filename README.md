# pythinfer - Python Logical Inference

[![Tests](https://github.com/robertmuil/pythinfer/actions/workflows/test.yml/badge.svg)](https://github.com/robertmuil/pythinfer/actions)
[![codecov](https://codecov.io/github/robertmuil/pythinfer/graph/badge.svg?token=VYLBQK488J)](https://codecov.io/github/robertmuil/pythinfer)

*Pronounced 'python fur'.*

CLI to easily merge multiple RDF files, perform inference (OWL or SPARQL), and query the result.

Point this at a selection of RDF files and it will merge them, run inference over them, export the results, and execute a query on them. The results are the original statements together with the *useful* set of inferences (see below under `Inference` for what 'useful' means here).

A distinction is made between 'external' and 'internal' files. See below.

## Quick Start

### Using `uv`

(in the below, replace `~/git` and `~/git/pythinfer/example_projects/eg0-basic` with folder paths on your system, of course)

1. Clone the repository:

   ```bash
   cd ~/git
   git clone https://github.com/robertmuil/pythinfer.git
   ```

1. Execute it as a tool in your project:

    ```bash
    cd ~/git/pythinfer/example_projects/eg0-basic
    uvx ~/git/pythinfer query "SELECT * WHERE { ?s ?p ?o } LIMIT 10"
    uvx ~/git/pythinfer query select_who_knows_whom.rq
    ```

    This will create a `pythinfer.yaml` project file in the project folder, merge all RDF files it finds, perform inference, and then execute the SPARQL query against the inferred graph.

1. Edit the `pythinfer.yaml` file to specify which files to include, try again. Have fun.

![Demo of executing eg0 in CLI](demo-eg0.gif)

## Command Line Interface

### Common Options

- `--extra-export`: allows specifying extra export formats beyond the default trig. Can be used to 'flatten' quads to triples when exporting (by exporting to ttl or nt as well as trig)
  - NB: `trig` is always included as an export because it is used for caching
- ...

### `pythinfer create`

Create a new project specification file in the current folder by scanning for RDF files.

Invoked automatically if another command is used and no project file exists already.

### `pythinfer merge`

Largely a helper command, not likely to need direct invocation.

### `pythinfer infer`

Perform merging and inference as per the project specification, and export the resulting graphs to the output folder.

### `pythinfer query`

A simple helper command should allow easily specifying a query, or queries, and these should be executed against the latest full inferred graph.

In principle, the tool could also take care of dependency management so that any change in an input file is automatically re-merged and inferred before a query...

## Project Specification

A 'Project' is the specification of which RDF files to process and configuration of how to process them, along with some metadata like a name.

Because we will likely have several files and they will be of different types, it is easiest to specify these in a configuration file (YAML or similar) instead of requiring everything on the command line.

The main function or CLI can then be pointed at the project file to easily switch between projects. This also allows the same sets and subsets of inputs to be combined in different ways with configuration.

### Project Specification Components

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
data:
    - <pattern>: <a pattern specifying a specific or set of files>
    - ...
    reference:
        - <pattern>: <a pattern specifying a specific or set of external files>
        - ...
output:
    folder: <a path to the folder in which to put the output> (defaults to `<base_folder>/derived`)
```

#### External vs Internal (Reference vs. Local)

External files are treated as ephemeral sources used for inference and then discarded. They are those that are not maintained by the user of the library, and whose axioms can generally be assumed to hold true for any application. They are used to provide inference rules, but are not part of the data being modelled, and they are not generally needed in the output.

Examples are OWL, RDFS, SKOS, and other standard vocabularies.

Synonyms for 'external' here could be 'transient' or 'reference' or 'catalyst'.

Need better term than 'internal' because it can be data (incl. vocabs and models) that are maintained outside of the project folder itself, but are desired to be part of the output. Perhaps 'local'.

### Path Resolution

Paths in the project configuration file can be either **relative or absolute**.

**Relative paths** are resolved relative to the directory containing the project configuration file (`pythinfer.yaml`). This allows project configurations to remain portable - you can move the project folder around or share it with others, and relative paths will continue to work.

This means that the current working directory from which you execute pythinfer is irrelevant - as long as you point to the right project file, the paths will be resolved correctly.

**Absolute paths** are used as-is without modification.

#### Examples

If your project structure is:

```ascii
my_project/
├── pythinfer.yaml
├── data/
│   ├── file1.ttl
│   └── file2.ttl
└── vocabs/
    └── schema.ttl
```

Your `pythinfer.yaml` can use relative paths:

```yaml
name: My Project
data:
  - data/file1.ttl
  - data/file2.ttl
internal_vocabs:
  - vocabs/schema.ttl
```

These paths will be resolved relative to the directory containing `pythinfer.yaml`, so the configuration is portable.

You can also use absolute paths if needed:

```yaml
data:
  - /home/user/my_project/data/file1.ttl
```

### Project Selection

The project selection process is:

1. **User provided**: path to project file provided directly by user on command line, and if this file is not found, exit
    1. if no user-provided file, proceed to next step
1. **Discovery**: search in current folder and parent folders for project file, returning first found
    1. if no project file discovered, proceed to next step
1. **Creation**: generate a new project specification by searching in current folder for RDF files
    1. if no RDF files found, fail
    1. otherwise, create new project file and use immediately

### Project Discovery

If a project file is not explicitly specified, `pythinfer` should operate like `git` or `uv` - it should search for a `pythinfer.yaml` file in the current directory, and then in parent directories up to a limit.

The limit on ancestors should be:

1. don't traverse below `$HOME` if that is in the ancestral line
1. don't go beyond 10 folders
1. don't traverse across file systems

### Project Creation

If a project is not provided by the user or discovered from the folder structure, a new project sepecification will be created automatically by scanning the current folder for RDF files. If some RDF files are found, subsidiary files such as SPARQL queries for inference are also sought and a new project specification is created. This new spec will be saved to the current folder.

The user can also specifically request the creation of a new project file with the `create` command.

## Merging

Merging of multiple graphs should preserve the source, ideally using the named graph of a quad.

Merging should also distinguish 3 different types of input:

1. 'external' vocabularies - things like OWL, SKOS, RDFS, which are introduced for inference purposes, but are not maintained by the person using the library, and the axioms of which can generally be assumed to exist for any application.
1. 'internal' vocabularies - ontologies being developed, vocabularies that are part of the

## Inference

By default an efficient OWL rule subset should be used, like OWL-RL.

### Invalid inferences

Some inferences, at least in `owlrl`, may be invalid in RDF - for instance, a triple with a literal as subject. These should be removed during the inference process.

### Unwanted inferences

In addition to the actually invalid inferences, many inferences are banal. For instance, every instance could be considered to be the `owl:sameAs` itself. This is semantically valid but useless to express as an explicit triple.

Several classes of these unwanted inferences can be removed by this package. Some can be removed per-triple during inference, others need to be removed by considering the whole graph.

#### Per-triple unwanted inferences

These are unwanted inferences that can be identified by looking at each triple in isolation. Examples:

1. triples with an empty string as object
2. redundant reflexives, such as `ex:thing owl:sameAs ex:thing`
3. many declarations relating to `owl:Thing`, e.g. `ex:thing rdf:type owl:Thing`
4. declarations that `owl:Nothing` is a subclass of another class (NB: the inverse is *not* unwanted as it indicates a contradiction)

#### Whole-graph unwanted inferences

These are unwanted inferences that can only be identified by considering the whole graph. Examples:

1. Undeclared blank nodes
   - blank nodes are often used for complex subClass or range or domain expressions
   - where this occurs but the declaration of the blank node is not included in the final output, the blank node is useless and we are better off removing any triples that refer to it
   - a good example of this is `skos:member` which uses blank nodes to express that the domain and range are the *union* of `skos:Concept` and `skos:Collection`
   - for now, blank node 'declaration' is defined as any triple where the blank node is the subject

### Inference Process

Steps:

1. **Load and merge** all input data into a triplestore
    - Maintain provenance of data by named graph
    - Maintain list of which named graphs are 'external'
    - output:        `merged`
    - consequence:   `current = merged`
2. **Generate external inferences** by running RDFS/OWL-RL engine over 'external' input data[^1]
    - output:        `inferences_external_owl`
3. **Generate full inferences** by running RDFS/OWL-RL inference over all data so far[^1]
    - output:        `inferences_full_owl`
    - consequence:   `current += inferences_full_owl`
4. **Run heuristics**[^2] over all data
    - output:        `inferences_sparql` + `inferences_python`
    - consequence:   `current += inferences_sparql` + `inferences_python`
5. **Repeat steps 3 through 4** until no new triples are generated, or limit reached
    - consequence:   `combined_full = current`
6. **Subtract external data and inferences** from the current graph[^4]
    - consequence:   `current -= (external_data + inferences_external_owl)`
    - consequence:   `combined_internal = current`
7. Subtract all 'unwanted' inferences from result[^3]
    - consequence:   `combined_wanted = current - inferences_unwanted`

[^1]: inference is backend dependent, and will include the removal of *invalid* triples that may result, e.g. from `owlrl`
[^2]: See below for heuristics.
[^3]: unwanted inferences are those that are semantically valid but not useful, see below
[^4]: this step logically applies, but in the `owlrl` implementation we can simply avoid including the external_owl_inferences graph in the output, since `owlrl` will not generate inferences that already exist.

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

## Data Structures

### DatasetView

Intended to give a restricted (filtered) view on a Dataset by only providing access to explicitly selected graphs, enabling easy handling of a subset of graphs without copying data to new graphs.

Specifications:

1. A DatasetView may be read/write or readonly.
1. Graphs MUST be explicitly included to be visible, otherwise they are excluded (and invisible).
1. Attempted access to excluded graphs MUST raise a PermissionError.
1. Any mechanism to retrieve triples (e.g.: iterating the view itself, or using `triples()` or using `quads()`) that does not explicitly specify a named graph (e.g. `triples()` called without a `context` argument) MUST return triples from all included graphs, not just the default graph.
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

## Real-World Usage

The `example_projects` folder contains contrived examples, but this has also been run over real data:

1. [foafPub](https://ebiquity.umbc.edu/resource/html/id/82/foafPub-dataset)
   1. takes a while, but successfully completes
   2. only infers 7 new useful triples, all deriving from an `owl:sameAs` link to an otherwise completely unconnected local id (treated as a blank node)
1. [starwars](https://platform.ontotext.com/semantic-objects/_downloads/2043955fe25b183f32a7f6b6ba61d5c2/SWAPI-WD-data.ttl)
   1. successfully completes, reasonable time
   2. infers 175 new triples from the basic starwars.ttl file, mainly that characters are of type `voc:Mammal` and `voc:Sentient` or `voc:Artificial`, etc.
      1. also funnily generates `xsd:decimal owl:disjointWith xsd:string`
   3. including `summary.ttl` doesn't change the inferences, which I think is correct.

## Next Steps

1. implement pattern support for input files
1. check this handles non-turtle input files ok
1. allow Python-coded inference rules (e.g. for path-traversal or network analytics)
    - also use of text / linguistic analysis would be a good motivation (e.g. infer that two projects are related if they share similar topics based on text analysis of abstracts)
1. implement base_folder support - perhaps more generally support for specification of any folder variables...
1. consider using a proper config language like dhal(?) instead of yaml
1. check and raise error or at least warning if default_union is set in underlying Dataset of DatasetView
1. document and/or fix serialisation: canon longTurtle is not great with the way it orders things, so we might need to call out to riot unfortunately.
1. consider changing the distinction from interal/external to data/vocabulary (where vocab includes taxonomies or ontologies) - basically the ABox/TBox distinction where CBox is part of TBox.
1. add support for ASK query
