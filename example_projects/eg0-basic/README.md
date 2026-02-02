# eg0-basic

Very basic example project to demonstrate usage.

This is also used in the test suite to verify the `create` command, so it is deliberately lacking a `pythinfer.yaml` file.

This example tests the following functionality:

1. Loading data and model files.
1. Using a symmetric property axiom to infer new triples.
1. Running queries against the inferred data.
1. Adding custom inference rules via SPARQL CONSTRUCT queries.

## Data

In this folder are two files which define a very simple graph of who knows whom (common prefixes ommitted):

### `basic-model.ttl`

```turtle
foaf:knows a owl:SymmetricProperty .
```

### `basic-data.ttl`

```turtle
:Alice rdf:type foaf:Person ;
    foaf:name "Alice Smith" ;
    foaf:age 30 .

:Bob rdf:type foaf:Person ;
    foaf:name "Bob Jones" ;
    foaf:knows :Alice .
```

## Querying

Also present is a SPARQL query file (`select_who_knows_whom.rq`) which lists who knows whom from the files:

```sparql
SELECT ?who ?whom
{
    ?who foaf:knows ?whom
}
```

Queried without inference, only a single result is returned (Bob knows Alice):

```sh
arq --data=basic-data.ttl --data=basic-model.ttl --query=select_who_knows_whom.rq
-----------------
| who  | whom   |
=================
| :Bob | :Alice |
-----------------
```

With inference enabled, the symmetric property axiom allows the inference engine to deduce that Alice also knows Bob, resulting in two results:

```sh
uv run pythinfer query select_who_knows_whom.rq
...
┏━━━━━━━━┳━━━━━━━━┓
┃ who    ┃ whom   ┃
┡━━━━━━━━╇━━━━━━━━┩
│ :Bob   │ :Alice │
│ :Alice │ :Bob   │
└────────┴────────┘
```

## Custom Inference Rules

To demonstrate custom inference rules with SPARQL, a CONSTRUCT query `infer_celebrity.rq` is include which infers that anyone older than 29 who knows Bob also knows Jamiroquai.

```sh
uv run pythinfer query --no-cache --project pythinfer_celebrity.yaml select_who_knows_whom.rq
```

NB: beware of [bug #33](https://github.com/robertmuil/pythinfer/issues/33): hence the `--no-cache` flag.