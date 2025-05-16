# telegraf-mqtt-tests

Testing if measurements get lost in a mqtt --> telegraf --> influxdb setup.

## Overview

Telegraf is configured with a mqtt consumer, a file output and a influxdb output. See [telegraf.conf](telegraf.conf)
The tester sends mqtt messages to mosquitto and collects these statistics:
* mqtt_sent: mqtt msgs sent
* mqtt_received: mqtt msgs received via tester on mqtt itself
* telegraf_mqtt_received: mqtt messages received by telegraf, detected via debug log
* telegraf_file_output_written: measurements written to file output
* telegraf_influxdb_output_written: measurements written to influxdb

```
   +--------------------------------------------------------------------+--+--+
   |                                                                    |  |  |
   |                                                                    |  |  |
   v                                                                    |  |  |
+------+                                                +-----------+   |  |  |
|tester|<-------+                          +----------->|logfile    +---+  |  |
+--+---+        |                          |            +-----------+      |  |
   |            |                          |                               |  |
   |            |                          |                               |  |
   |         +--+--------+          +------+-+          +-----------+      |  |
   |         |mosquitto  |          |telegraf|          |influxdb   |      |  |
   +-------->|mqtt server+--------->|        +--------->|output     +------+  |
             +-----------+          +------+-+          +-----------+         |
                                           |                                  |
                                           |            +-----------+         |
                                           +------------>file output+---------+
                                                        +-----------+          
```

## Prerequisites

* Influxdb server
* API token with read/write access to bucket

## Configuration

Copy [template.env](template.env) to `.env`. Modify all `INFLUX_xxxx` variables according to your setup.

## Running

```bash
docker compose up --build
```
