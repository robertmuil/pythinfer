# EG2 - Projects

NB: if this matures, we might move the model into a more prominent and utilised place rather than just being an example.

This should *not* include a `pythinfer.yaml` project file, because one of the test cases that use this example is to test automatic project creation.

## Supported Tests

### Related Projects - Complex Inference with SPARQL

Determine a weighted link between any two projects, based on multiple dimensions, and then apply a threshold to decide if they should be considered 'Related'

### Flattening Related Projects - OWL-RL inference to simplify querying

Projects are related via a reified `Project Relationship` node, which makes querying and traversal indirect.

The purpose of this is to use OWL-RL property-chain axioms to infer a direct link between projects, `ptp:relatedProject`, from the presence of the `Project Relationship` node.

