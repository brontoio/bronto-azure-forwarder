import logging
import urllib.request
import gzip
import time
import json
import os
from typing import Optional

import azure.functions as func

DEFAULT_ACTIVITY_LOGS_COLLECTION = 'AZActivityLogs'
ACTIVITY_LOGS_CATEGORIES = ['Administrative', 'Policy']
ENTRA_ID_CATEGORIES = ['AuditLogs', 'ProvisioningLogs', 'UserRiskEvents', 'SignInLogs']

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

FORWARDER_NAME = os.environ.get('FORWARDER_NAME', 'brontoForwarder')


class ConfigurationException(Exception):
    pass


class Config:

    def __init__(self):
        self.default_collection = os.environ.get('BRONTO_COLLECTION')
        self.default_dataset =  os.environ.get('BRONTO_DATASET')
        log_attributes_raw = os.environ.get('LOG_ATTRIBUTES', '')
        log_attributes_split = list(map(lambda x : x.split('='), log_attributes_raw.split(',')
                                        if log_attributes_raw else []))
        self.log_attributes = {}
        self.log_attributes = {item[0]: item[1] for item in log_attributes_split
                               if len(item) == 2 and item[0] and item[1]}


        self.bronto_ingestion_endpoint = os.environ.get('BRONTO_INGESTION_ENDPOINT')
        if not self.bronto_ingestion_endpoint:
            raise ConfigurationException('BRONTO_INGESTION_ENDPOINT is not a valid Bronto endpoint')
        self.bronto_api_key = os.environ.get('BRONTO_API_KEY')
        if not self.bronto_api_key:
            raise ConfigurationException('BRONTO_API_KEY is not a valid API Key')
        self.max_payload_size = os.environ.get('MAX_BRONTO_PAYLOAD_SIZE_BYTES', 5_000_000)


class BrontoDestinationProvider:

    def __init__(self, default_collection=None, default_dataset=None):
        self.collection = default_collection
        self.dataset = default_dataset

    def get_collection(self, entry) -> Optional[str]:
        category = entry.get('Category')
        if category is None:
            category = entry.get('category')
        if category is None:
            return self.collection
        if category in ACTIVITY_LOGS_CATEGORIES:
            return DEFAULT_ACTIVITY_LOGS_COLLECTION
        elif category == 'FunctionAppLogs':
            return category
        elif category.lower().startswith('nsp'):
            return 'NetworkSecurityPerimeter'
        elif category in ENTRA_ID_CATEGORIES:
            return 'EntraID'
        elif category.lower().startswith('advancedhunting'):
            return 'MSDefender'
        return self.collection

    def get_dataset(self, entry) -> Optional[str]:
        category = entry.get('Category')
        if category is None:
            category = entry.get('category')
        if category is None:
            return self.dataset
        if category in ACTIVITY_LOGS_CATEGORIES:
            return category
        elif category == 'FunctionAppLogs':
            return entry.get('appName')
        elif category.startswith('Nsp'):
            return 'AccessLogs'
        elif category.startswith('nsp'):
            return 'ProfilesLogs'
        elif category in ENTRA_ID_CATEGORIES:
            return category
        elif category.lower().startswith('advancedhunting'):
            return category
        return self.dataset


class BrontoClient:

    def __init__(self, destination_provider: BrontoDestinationProvider, config: Config):
        self.dest_provider = destination_provider
        self.max_payload_size = config.max_payload_size
        self.ingestion_endpoint = config.bronto_ingestion_endpoint
        self.api_key = config.bronto_api_key
        self.log_attributes = config.log_attributes
        self.headers = {
            'Content-Encoding': 'gzip',
            'Content-Type': 'application/json',
            'User-Agent': 'Fluent-Bit',   # TODO: update ingestion to support a dedicated user agent, e.g. bronto-azure-forwarder
            'x-bronto-api-key': self.api_key
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

    def enrich(self, entry):
        entry_w_attrs = {'log': entry}
        entry_w_attrs.update({k: v for k,v in self.log_attributes})
        collection = self.dest_provider.get_collection(entry)
        if collection:
            entry_w_attrs.update({'service.namespace': collection})
        dataset = self.dest_provider.get_dataset(entry)
        if dataset:
            entry_w_attrs.update({'service.name': dataset})
        return entry_w_attrs

    def send_data(self, batch):
        data = '\n'.join([json.dumps(self.enrich(entry)) for entry in batch])
        compressed_data = gzip.compress(data.encode())
        if len(compressed_data) < self.max_payload_size:
            logging.info('Batch compressed. compressed_batch_size=%s', len(compressed_data))
            self._send_batch(compressed_data)
            return
        logging.warning('Compressed batch is too large. Splitting in half. compressed_batch_size=%s, max_compressed_batch=%s', 
                        len(compressed_data), self.max_payload_size)
        batch_size = len(batch)
        half = int(batch_size / 2)
        self.send_data(batch[:half])
        self.send_data(batch[half:])


@app.function_name(name=FORWARDER_NAME)
@app.event_hub_message_trigger(arg_name="azeventhub", event_hub_name="%EVENTHUB_NAME%",
                               connection="EVENTHUB_CONNECT_STRING")
def forward(azeventhub: func.EventHubEvent):
    config = Config()
    data = azeventhub.get_body().decode('utf-8')
    try:
        data = json.loads(data)
    except json.decoder.JSONDecodeError as _:
        logging.info('EVENT=%s', data)
        data = {'records' : [{'Category': 'unsupported', 'Message': data}]}
    if type(data) == list:
        logging.warning('Unexpected payload type: lists are not accepted. Maybe some unsupported input sources are generating log data.')
        return
    default_collection = config.default_collection
    default_dataset = config.default_dataset
    destination_provider = BrontoDestinationProvider(default_collection, default_dataset)
    bronto_client = BrontoClient(destination_provider, config)
    records = data.get('records')
    if records is None:
        logging.warning('No records in message')
        return
    elif type(records) != list:
        logging.warning('list type expected for `records`. found_type=%s', type(records).__name__)
    bronto_client.send_data(records)
