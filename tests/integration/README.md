# Integration Tests

Should test a set of cohesive functions together, or a function with external dependencies (such as filesystem). They should focus on a subset of the packages functionality.

In general, dependencies external to the package should be mocked, but it is also valuable in some cases to test explicitly the interaction with external dependencies.