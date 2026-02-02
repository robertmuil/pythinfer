# eg0-basic

Very basic example project to demonstrate usage.

This is also used in the test suite to verify the `create` command, so it is deliberately lacking a `pythinfer.yaml` file.

## Contents

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

### `select_who_knows_whom.rq`

Also present is a SPARQL query file which lists who knows whom from the files:

```sparql
SELECT ?who ?whom
{
    ?who foaf:knows ?whom
}
```

## Operation

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
