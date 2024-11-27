import logging
import urllib.request
import gzip
import time
import json
import os
import azure.functions as func

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

COLLECTION = os.environ.get('COLLECTION')
DATASET = os.environ.get('DATASET')
BRONTO_INGESTION_ENDPOINT = os.environ.get('BRONTO_INGESTION_ENDPOINT')
BRONTO_API_KEY = os.environ.get('BRONTO_API_KEY')
MAX_PAYLOAD_SIZE = os.environ.get('MAX_BRONTO_PAYLOAD_SIZE', 10_000_000)


class BrontoClient:

    def __init__(self):
        self.api_key = BRONTO_API_KEY
        self.ingestion_endpoint = BRONTO_INGESTION_ENDPOINT
        self.headers = {
            'Content-Encoding': 'gzip',
            'Content-Type': 'application/json',
            'User-Agent': 'bronto-azure-forwarder',
            'x-bronto-api-key': self.api_key,
            'x-bronto-log-name': DATASET,
            'x-bronto-logset': COLLECTION
        }

    def _send_batch(self, compressed_batch):
        request = urllib.request.Request(self.ingestion_endpoint, data=compressed_batch, headers=self.headers)
        attempt = 0
        max_attempts = 5
        with urllib.request.urlopen(request) as resp:
            if resp.status != 200 and attempt < max_attempts:
                attempt += 1
                delay_sec = attempt * 10
                logging.warning('Data sending failed. attempt=%s, max_attempts=%s, status=%s, reason=%s',
                                attempt, max_attempts, resp.status, resp.reason)
                time.sleep(delay_sec)
                self._send_batch(compressed_batch)

    def send_data(self, batch):
        data = '\n'.join([json.dumps(entry) for entry in batch])
        compressed_data = gzip.compress(data.encode())
        if len(compressed_data) < MAX_PAYLOAD_SIZE:
            logging.info('Batch compressed. compressed_batch_size=%s', len(compressed_data))
            self._send_batch(compressed_data)
            return
        logging.warning('Compressed batch is too large. Splitting in half. compressed_batch_size=%s, max_compressed_batch=%s', 
                        len(compressed_data), MAX_PAYLOAD_SIZE)
        batch_size = len(batch)
        half = int(batch_size / 2)
        self.send_data(data, batch[:half])
        self.send_data(data, batch[half:])


@app.function_name(name='brontologforwarder')
@app.event_hub_message_trigger(arg_name="azeventhub", event_hub_name="loggenerators",
                               connection="<EVENT_HUB_CONNECTION_SETTINGS_KEY>")  # See local.settings.json for an example
def forward(azeventhub: func.EventHubEvent):
    data = azeventhub.get_body().decode('utf-8')
    data = json.loads(data)
    bronto_client = BrontoClient()
    bronto_client.send_data(data.get('records', []))
