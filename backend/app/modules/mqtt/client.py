import json
import logging
import time
import uuid

import paho.mqtt.client as mqtt

from app.database.session import SessionLocal, settings
from app.modules.mqtt.service import process_challenge

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

BASE_TOPIC = f"fse-01/{settings.mqtt_candidate_id}"
CHALLENGE_TOPIC = f"{BASE_TOPIC}/challenge"
RESPONSE_TOPIC = f"{BASE_TOPIC}/response"
STATUS_TOPIC = f"{BASE_TOPIC}/status"


def publish_status(client: mqtt.Client, status: str) -> None:
    payload = {
        "candidate_id": settings.mqtt_candidate_id,
        "status": status,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    info = client.publish(
        STATUS_TOPIC,
        json.dumps(payload),
        qos=1,
        retain=False,
    )

    if info.rc != mqtt.MQTT_ERR_SUCCESS:
        logger.warning("Could not queue status %s: rc=%s", status, info.rc)


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code.is_failure:
        logger.error("MQTT connection failed: %s", reason_code)
        return

    logger.info("Connected to MQTT broker")

    result, _ = client.subscribe(CHALLENGE_TOPIC, qos=1)
    if result != mqtt.MQTT_ERR_SUCCESS:
        logger.error("Could not subscribe to %s: rc=%s", CHALLENGE_TOPIC, result)
        return

    logger.info("Subscribed to %s", CHALLENGE_TOPIC)
    publish_status(client, "ONLINE")


def on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
    logger.warning(
        "MQTT disconnected: reason=%s, flags=%s",
        reason_code,
        disconnect_flags,
    )


def on_message(client, userdata, message):
    logger.info("Challenge received on %s", message.topic)

    try:
        payload = json.loads(message.payload.decode("utf-8"))

        if not isinstance(payload, dict):
            raise ValueError("Challenge payload must be a JSON object")

        with SessionLocal() as db:
            response = process_challenge(db, payload)

        client.publish(
            RESPONSE_TOPIC,
            json.dumps(response),
            qos=1,
            retain=False,
        )

        logger.info(
            "Challenge %s processed with status %s",
            response.get("challenge_id"),
            response.get("status"),
        )

    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        logger.warning("Invalid challenge payload: %s", exc)

        response = {
            "challenge_id": None,
            "status": "FAILED",
            "results": [],
            "error": str(exc),
        }

        client.publish(
            RESPONSE_TOPIC,
            json.dumps(response),
            qos=1,
            retain=False,
        )

    except Exception:
        logger.exception("Unexpected error while processing challenge")


def main():
    client_id = f"fse01-{settings.mqtt_candidate_id}-" f"{uuid.uuid4().hex[:8]}"

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=client_id,
        protocol=mqtt.MQTTv311,
    )

    offline_payload = json.dumps(
        {
            "candidate_id": settings.mqtt_candidate_id,
            "status": "OFFLINE",
        }
    )

    client.will_set(
        STATUS_TOPIC,
        payload=offline_payload,
        qos=1,
        retain=False,
    )

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message

    client.reconnect_delay_set(min_delay=1, max_delay=30)

    try:
        logger.info(
            "Connecting to %s:%s as %s",
            settings.mqtt_broker_host,
            settings.mqtt_broker_port,
            client_id,
        )

        client.connect_async(
            settings.mqtt_broker_host,
            settings.mqtt_broker_port,
            keepalive=settings.mqtt_keepalive,
        )

        client.loop_forever(retry_first_connection=True)

    except KeyboardInterrupt:
        logger.info("Stopping MQTT client")

    except Exception:
        logger.exception("MQTT client stopped unexpectedly")

    finally:
        if client.is_connected():
            publish_status(client, "OFFLINE")
            client.disconnect()


if __name__ == "__main__":
    main()
