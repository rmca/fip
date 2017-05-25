.. design documentation master file, created by
   sphinx-quickstart on Fri May 19 14:52:50 2017.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to design's documentation!
==================================

.. toctree::
   :maxdepth: 2
   :caption: Contents:


Getting Started
===============

To spin up the solution you can run: docker-compose up

Then to create the database you need to run a few commands on the
Ingestion API or List API containers. The following commands are needed:

.. code-block:: bash

  flask db init

  flask db migrate

  flask db upgrade

For instance:

.. code-block:: bash

  docker exec ingestionapi_listapi_1 flask db init

  docker exec ingestionapi_listapi_1 flask db migrate

  docker exec ingestionapi_listapi_1 flask db upgrade

To run tests you can install the requirements and then run nosetests like so:

.. code-block:: bash

 SQLALCHEMY_DATABASE_URI='sqlite:///foo.db' nosetests -s 

Once the docker containers are up and the database has been built, you can open
the index.html file and click the link to have it connect to the web socket
server.

To create some messages and see them arrive at the REST API and HTML page, you can run:

.. code-block:: bash

  python scripts/end_to_end.py

Requirements
============

We have a number of requirements that this design must meet:

- A Readme file containing information you deem useful for someone getting to
  know your code and want to try the system out

- Develop the application in Python 3

- A REST endpoint is taking a dummy JSON input, and the server puts the REST
  payload on Redis or another tool you think is well suited for the task

- A Consumer is running in the application, taking the freshly received message
  and persists it in a database of your choice

- A REST endpoint is implemented for retrieving all the messages persisted in
  JSON format from the database

- The message should also be pushed through Websockets for listening browser
  clients at the time the message was received on the REST endpoint

- A simple HTML page is implemented to show the real time message delivery

- Please setup a github repository to host the code and share it with your
  final note for review


Components Overview
===================

Ingestion API (ingestion_api.py). 
---------------------------------

This is a user-facing API for accepting messages (sometimes referred to in
the docs/code as dummy messages). This component is mainly responsibly for
taking the incoming messages and adding them to the Redis task queue.
Additionally it publishes incoming messages to a pubsub topic for the
websocket server to consume.

Celery Queue (tasks.py)
-----------------------

This is the task processor that takes messages from the task queue and
persists them to the database.

Websocket server (wsserver.py)
------------------------------

This server takes messages from the pubsub topic the ingestion API
publishes to, and broadcasts them to websocket clients. The point of this
server is to fan out messages from the pubsub queue to many clients
without Redis incurring the overhead of having too many client
connections.

List API (list_api.py)
----------------------

An API for listing messages received from the client. This allows
interested parties to paginate through all of the messages received.

Database Models (db.py)
-----------------------

The database model code lives in db.py. This also provides the migrations
interface via flask-migrations.

Tests
-----

These live in tests.py. There are also end to end tests in
scripts/end_to_end.py. I have also provided a script for adding lots of
records (make_sample_records.py) and iterating over result set
(test_pagination.py). The test_pagination.py script was used to somewhat
verify that the SQL query we use to paginate doesn't grow in query time as
we paginate further through the results set.

Basic Design
============

The REST API for accepting incoming messages (Ingestion API), is a Flask
app. Incoming data will be received from a client, and first written to a
Redis queue as a persistence job (Celery task queue).  A Celery app will
monitor the queue and consume jobs for persisting to the database. Once a
job has been written to the incoming message queue by the REST API, it
will then be written to a pubsub service (for simplicity, also Redis),
which a websocket service will monitor and push to connected clients.

A second REST API will allow messages to be retrieved from the database. This
API will also be a Flask app, and will allow clients to page through the logs
in the order in which they are persisted.

Ingestion API
==========================

The incoming message API exposes a /dummy interface for creating a new
dummy resource via a POST request. When we accept a new message we try to
write it to the incoming message queue (Redis). A successful write to this
message queue allows us to signal to the client that it was accepted (HTTP
status 202). We use a 202 status to indicate that the resource will be
created at some time in the future, and so may not be immediately available. 

Before we return to the client we try to write to the pubsub service. The
pubsub service write can fail and we will still return success to the
client; message delivery here is best effort. We assume this is acceptable
since the Websocket interface doesn't provide a resume feature and isn't
meant to be considered an authoritative source of the incoming message
data. Also clients could miss data if they were disconnected temporarily.

If clients wish to retrieve the full contents of the database, they should
use the List API provided. We drop messages to avoid slow clients from
causing a backlog of messages in the Websocket server. An alternative
strategy here might be to disconnect slow clients, so that they hopefully
reconnect and process messages more quickly, or stay disconnected.

Message Broker
==============

We assume that Redis is run with persistence turned on with at least the following settings:

.. code-block:: ini

  appendonly yes
  maxmemory-policy noeviction

While the delivered solution only has a single Redis server, to avoid
failures from resulting in missing messages we would need to turn
replication on. Since Redis replication is asynchronous, to avoid message
loss, we could either force an fsync after every write (taking a
performance hit), otherwise log the message (e.g. on the local filesystem
of the ingestion API servers) so that it can be replayed after an outage,
or replicate the message to multiple masters.


Websocket Server
================

I wrote this using asyncio, since it seems like a perfect application for
that library i.e. IO bound task with many clients. As mentioned before the
point of this is to allow us to support many more websocket clients than
we could otherwise handle using a single process/single client scenario.

Database Design
===============

Since the List API potentially needs to allow clients to iterate over the
entire data set, I wanted to avoid a situation where the query time grew
as the result of a limit/offset pagination strategy. Instead I decided to
timestamp the messages at the time of write and include a message ID (for
now a UUID). This allows us to uniquely identify each message and achieve
an ordering for iteration. I'm ok with the fact that the Celery workers
write the timestamp, and any clock drift between different Celery machines
shouldn't matter. The point of the timestamp is really just to allow us to
iterate in a deterministic way over the data set.

Failures
========

The types of failures handled by this solution is by no means complete.
Some future issues that would need to be resolved include:

- Rate limiting requests to the ingestion API. Since we have no concept of a
  user, the only thing we could do right now is to rate limit by client
  host. We would need to prevent a client either maliciously or
  accidentally creating a bunch of tasks and filling up our queues.

- A single database with no support for sharding at the moment means that
  if MySQL goes down we need to bring it back up to allow writes to
  proceed. An alternate strategy would allow us to discover a list of
  available MySQL servers via some kind of service discovery and ignore
  unavailable ones e.g. with circuit breakers.

- Technically a queue can back up if its tasks keep failing. This would impede
  progress on the backlog. For now we just let the queue grow. Eventually it
  would be nice to offload constantly failing tasks to a secondary queue that
  persists to disk rather than memory.

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
