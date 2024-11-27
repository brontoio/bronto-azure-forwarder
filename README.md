## Bronto Azure Log Forwarder

This project contains an Azure app function definition, which serves as a log forwarder. The function gets log events from [Azure Event Hub](https://learn.microsoft.com/en-us/azure/event-hubs/) and forwards them to [Bronto](https://bronto.io).


### Configuration
The function requires the following configuration via environment variables:

- COLLECTION: the name of the Bronto Collection to forward the log data to, e.g. `Azure`
- DATASET: the name of the Bronto Dataset (within the Collection defined above) to forward the log data to, e.g. `EventHub`
- BRONTO_INGESTION_ENDPOINT: the Bronto ingestion endpoint (depends on the region where the Bronto organisation is setup), e.g. `https://ingestion.eu.bronto.io`
- BRONTO_API_KEY: the Bronto API key required to authenticate when sending data to the ingestion endpoint.

The function also requires for the relevant Event Hub connection to be configured. This step is detailed in the [Deployment section](#deployment).

### Deployment
This function can be deployed by cloning this repository and using the [VSCode - Azure extensions](https://code.visualstudio.com/docs/azure/overview). Deployment from VSCode can be performed as explained [here](https://learn.microsoft.com/en-us/azure/azure-functions/functions-develop-vs-code?tabs=node-v4%2Cpython-v2%2Cisolated-process%2Cquick-create&pivots=programming-language-python#republish-project-files). 

This function acts as an Event Hub trigger. Information on how to configure such python functions can be found [here](https://learn.microsoft.com/en-us/azure/azure-functions/functions-bindings-event-hubs-trigger?tabs=python-v2%2Cisolated-process%2Cnodejs-v4%2Cfunctionsv2%2Cextensionv5&pivots=programming-language-python). This function `event_hub_message_trigger` and the `local.settings.json` files need to be updated in order to set the trigger [connection](https://learn.microsoft.com/en-us/azure/azure-functions/functions-bindings-event-hubs-trigger?tabs=python-v2%2Cisolated-process%2Cnodejs-v4%2Cfunctionsv2%2Cextensionv5&pivots=programming-language-python#decorators), i.e. replace `EVENT_HUB_CONNECTION_SETTINGS_KEY` and `EVENT_HUB_CONNECTION_SETTINGS_VALUE` to match your Event Hub setup.
