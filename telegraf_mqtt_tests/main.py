import uuid
from dataclasses import dataclass
from os import getenv
from time import sleep
from typing import Callable

import paho.mqtt.client as mqtt
from influxdb_client import InfluxDBClient
from line_protocol_parser import parse_line

QOS = 1
TOPIC = "telegraf"

INFLUXDB_QUERY = """
from(bucket: "{INFLUX_BUCKET}")
  |> range(start: -5m)
  |> filter(fn: (r) => r["_measurement"] == "{TEST_ID}")
"""


def getenv_or_error(key: str) -> str:
    val = getenv(key)
    if val is None:
        raise ValueError(f"{key} must be set in ENV")
    else:
        return val


@dataclass
class Measurement:
    test_id: str
    measurement_id: int
    val: float
    offline: bool = False
    sent: bool = False
    mqtt_received: bool = False
    telegraf_file_output_written: bool = False
    telegraf_influxdb_output_written: bool = False

    def influx_line_protocol(self) -> str:
        if self.offline:
            offline_str = "true"
        else:
            offline_str = "false"
        return f"{self.test_id},measurement_id={str(self.measurement_id)},offline={offline_str} val={self.val}"  # noqa


def parse_mid_from_influx_line_protocol(influx_line_measurement: str) -> int:
    line_data = parse_line(influx_line_measurement)
    return int(line_data["tags"]["measurement_id"])


class Tester:
    measurements: dict[int, Measurement] = {}

    def __init__(self):
        self.test_id = str(uuid.uuid4())
        print(f"test_id: {self.test_id}")
        num = int(getenv_or_error("NUM_MEASUREMENTS"))
        for i in range(num):
            self.measurements[i] = Measurement(
                test_id=self.test_id, measurement_id=i, val=1
            )

        self.mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.mqttc.on_connect = self.on_connect
        self.mqttc.on_message = self.on_message

        self.mqttc.connect("localhost", 1883, 60)

        self.mqttc.loop_start()
        sleep(1)

        self.send_measurements()

        # wait for incoming mqtt
        sleep(5)
        self.mqttc.loop_stop()

        # wait for telegraf to write measurements to file
        delay = int(getenv_or_error("DELAY_BEFORE_CHECKS"))
        sleep(delay)

        self.check_telegraf_file_output()
        self.check_influxdb_output()
        self.report()

    @property
    def measurements_list(self):
        return list(self.measurements.values())

    def send_measurements(self):
        for measurement in self.measurements_list:
            self.mqttc.publish(TOPIC, measurement.influx_line_protocol(), qos=QOS)
            sleep(0.02)
            measurement.sent = True

    @staticmethod
    def telegraf_log_num_mqtt_msgs() -> int:
        num = 0
        file_path = getenv_or_error("TELEGRAF_LOG_FILE")
        with open(file_path, "r") as f:
            for line in f.readlines():
                if "startIncomingComms: received publish, msgId:" in line:
                    num += 1
        return num

    def check_telegraf_file_output(self):
        file_path = getenv_or_error("TELEGRAF_MEASUREMENTS_FILE")
        with open(file_path, "r") as f:
            for line in f.readlines():
                if self.test_id in line:
                    self.measurements[
                        parse_mid_from_influx_line_protocol(line)
                    ].telegraf_file_output_written = True

    def check_influxdb_output(self):
        client = InfluxDBClient(
            url=getenv_or_error("INFLUX_URL"),
            token=getenv_or_error("INFLUX_TOKEN"),
            org=getenv_or_error("INFLUX_ORG"),
        )
        query_api = client.query_api()
        csv_result = query_api.query_csv(
            INFLUXDB_QUERY.format(
                INFLUX_BUCKET=getenv_or_error("INFLUX_BUCKET"), TEST_ID=self.test_id
            )
        )
        for row in csv_result:
            print(row)
            if row[8] == self.test_id:
                val = int(row[-3])
                self.measurements[val].telegraf_influxdb_output_written = True

    def count_measurements_with_condition(
        self, condition: Callable[[Measurement], bool]
    ) -> int:
        count = 0
        for measurement in self.measurements_list:
            if condition(measurement):
                count += 1
        return count

    def report(self):
        print("Measurements statistics:")
        print(f"mqtt_sent: {self.count_measurements_with_condition(lambda m: m.sent)}")
        print(
            f"mqtt_received: {self.count_measurements_with_condition(lambda m: m.mqtt_received)}"  # noqa
        )
        print(f"telegraf_mqtt_received: {self.telegraf_log_num_mqtt_msgs()}")
        print(
            f"telegraf_file_output_written: {self.count_measurements_with_condition(lambda m: m.telegraf_file_output_written)}"  # noqa
        )
        print(
            f"telegraf_influxdb_output_written: {self.count_measurements_with_condition(lambda m: m.telegraf_influxdb_output_written)}"  # noqa
        )

    # The callback for when the client receives a CONNACK response from the server.
    def on_connect(self, client, userdata, flags, reason_code, properties):
        print(f"mqtt connected with result code {reason_code}")
        # Subscribing in on_connect() means that if we lose the connection and
        # reconnect then subscriptions will be renewed.
        client.subscribe(TOPIC)

    # The callback for when a PUBLISH message is received from the server.
    def on_message(self, client, userdata, msg):
        # print(msg.topic + " " + str(msg.payload))
        msg_str: str = msg.payload.decode()
        self.measurements[
            parse_mid_from_influx_line_protocol(msg_str)
        ].mqtt_received = True


def main():
    tester = Tester()  # noqa


if __name__ == "__main__":
    main()
