# Royo

Applying the Reo philosophy to Docker Compose. Very much a prototype.

## The idea

### Reo

A system can be understood as a set of components interacting according to some protocol. Standard programming practices lead to two issues:
- The components typically make assumptions about the environment and are therefore not properly modular. For instance, they may explicitly target other components with messages or assume the existence of certain locks.
- The protocol is implicit. E.g., to understand that two components are alternatingly accessing a resource in a mutually exclusive fashion, various code fragments must be inspected -- each providing an incomplete view -- from which the protocol is reconstructed. We might say that the protocol is defined 'from within', or 'endogenously'.

Reo is a coordination language that addresses these issues. A component may only interact with ports that exist at its boundary. Then the protocol is defined 'from without' or 'exogenously' as a Reo circuit. The protocol can now be more easily comprehended, and it can be reused and verified. Components are also more modular, since they no longer depend on their environment.

Tools exist that turn Reo specifications (e.g., 'A sends a datum to B') into executable code (e.g., socket communication for a particular language).

 A better and more comprehensive introduction (with plenty of visualizations) to Reo is available at [the Reo website](http://reo.project.cwi.nl/v2/).

 ### Docker Compose

 Docker containers abstract from the underlying operating system. Docker Compose is useful for linking Docker containers together. But it still suffers from some of the issues described above:

 - Any communication logic 
