# Royo

Applying the Reo philosophy to Docker Compose. Very much a proof of concept!

## The problem: background

### Reo

A system can be understood as a set of heterogenous components interacting according to some protocol. Standard programming practices lead to two issues:
- The components typically make assumptions about the environment and are therefore not properly modular. For instance, they may explicitly target other components with messages, implicitly assuming both that those components are present and that message-passing is the communication mechanism of the system.
- The protocol is implicit. E.g., to understand that two components are alternatingly accessing a resource in a mutually exclusive fashion, various code fragments must be inspected -- each providing an incomplete view -- from which the protocol is reconstructed in the mind of the programmer. We might say that the protocol is defined 'from within', or 'endogenously'.

Reo is a coordination language that addresses these issues. A component may only interact with ports that exist at its boundary. Then the protocol is defined 'from without' or 'exogenously' as a Reo circuit. The protocol can now be more easily comprehended, and it can be reused and verified. Components are also more modular, since they no longer depend on their environment.

Tools exist that turn Reo protocol specifications (e.g., 'A moves a datum to B') into executable code (e.g., socket communication for a particular language).

A better and more comprehensive introduction to Reo (with plenty of visualizations) is available at [the Reo website](http://reo.project.cwi.nl/v2/).

 ### Docker Compose

Docker containers abstract from the underlying operating system. The code in a container serves a particular computational task and may in principle be written in any programming language. Docker Compose is useful for linking Docker containers together. Docker Compose allows, e.g., referencing of other Docker containers by name within the `docker-compose.yaml` specification file.

Docker Compose does not overcome the issues described above. The _computation code_ in a container is still cluttered with _communication code_: which libraries to import, how to send a HTTP post request, which network port(s) to send it to, etc. As a result the protocol is still implicit. Moreover, the programmer has to manually establish the appropriate port mappings and start-up dependencies in the `docker-compose.yaml` file, which is error-prone.

## The solution: Royo

Royo is a language that applies some of the Reo philosophy in the domain of container orchestration. It is meant as a proof of concept and not nearly as rich as Reo. In particular, it supports only one channel, resembling an HTTP post request; it assumes that each container has exactly one input and one output port; and it cannot be used to construct complex protocols that involve synchronization. The intended use case for Royo is defining orchestrations in which data flows asynchronously through a DAG of containers. An advantage of Royo is that no external coordinator is needed.

Royo assumes certain container primitives, which are declaratively linked together in a `.royo` specification. The linking is performed by `composer.py`, which generates a target folder containing Docker images and a `docker-compose.yaml` file that can be executed in the usual way. We explain primitives, `.royo` files and `composer.py` in turn.

### Primitives

Royo relies on the existence of Docker images which are considered primitives. For purposes of demonstration, this repository contains six such Docker images in `docker_images`:
- `doubler`: doubles an integer from its input, puts it on output;
- `forwarder`: takes an integer from its input, puts it on output;
- `one_generator`: repeatedly generates a 1 and puts it on output;
- `paritychecker`: tests whether an integer on input is even, puts result on output;
- `reporter`: takes a JSON from input, prints its contents to standard output; and
- `rng`: repeatedly generates a random number and puts it on output.

Note that all data are wrapped in JSON objects.

`rng` is a Bash script; the other images are Ruby scripts. The scripts use macros
- `@ROYO_GET x` to wait for a JSON object on its input and bind it to variable `x`; and
- `@ROYO_PUT x` to put JSON object `x` on its output.

These macros are ultimately preprocessed by the composer `composer.py`, which injects the required communication code into each container as required by `.royo` specification

### `.royo` specification

The top-level dataflow specification is defined in a `.royo` file. We informally discuss some of its features, using `inflater.royo` as our leading example.

#### Instantiation

A line `name :: class` declares an (logical) container with name `name` as an instance of class `class`. In the most basic case, `class` is a Docker image primitive, living as a directory under `docker_images` (which is where `composer.py` will look), and `name` will be a container instance of that image at runtime. But Royo allows complex classes to be constructed out of simpler ones, as we will see below.

#### Linking

A line `name1 -> name2` links the output of `name1` to the input of `name2`. Outputs can be linked to arbitrarily many destinations.

Linking can be conditional. The syntax is `name1 -> name2 [ C ]`. `C` must be a condition on identifier `@ROYO_JSON`, where `@ROYO_JSON` will be replaced with the datum to be transmitted by `composer.py`. At present, there is no meta-syntax for the condition `C`: it must be a valid condition in the programming language associated with `name1`.

#### Complex classes

Consider the following example from `inflater.royo`:

```
quadrupler = {
  d1 :: doubler
  d2 :: doubler

  in d1
  out d2

  d1 -> d2
}
```

This declares a complex class `quadrupler`. It has two doublers living inside it, `d1` and `d2`. The input port of a `quadrupler` instance `q1` is the input port of `d1`, and the output port of `q1` is the output port of `d2`. Internally, the output of `d1` is forwarded to the input of `d2`.

Complex classes can be nested.

Complex classes disappear at runtime. If the above is instantiated as a quadrupler `q1`, then `doubler` containers `q1.d1` and `q1.d2` will exist at runtime. This naming convention is very hacky and may cause clashes, so the user should be careful.

### Composing using `composer.py`

File `composer.py` handles the actual preprocessing and linking. It generates a target folder `target` containing a `docker-compose.yaml` file and all the required post-processed Docker images.

It can presently handle only Ruby and Bash script primitives, and it can only inject linking conditions for Ruby. For instance, a `@ROYO_PUT` of JSON object `royo_json` in a Ruby file is replaced by:

```ruby
dests = ENV['DESTS'].split(',')
conds = ENV['CONDS'].split(',').map{|s| s.gsub(/@ROYO_JSON/, "royo_json")}
conds = conds.map{|s| if s.strip == "True" then "true" else s end}
dests.zip(conds).each{|dest, cond|
  if eval(cond) then
    HTTParty.post("http://" + dest, body: royo_json, :headers => {'Content-Type'=>'application/json'})
  end
}

200
```

The `DESTS` and `CONDS` environment variables are container-specific and set in `docker-compose.yaml`. Their values are derived from the Royo specification.

It is very much a write only script. Use with care.

## Try it

Run `python composer.py inflater.royo` in the root of the repository and inspect the contents of `target`. Run `docker-compose start` in `target` to start all containers.
