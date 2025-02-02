#!/bin/bash

ROOT_DIR="$(pwd)"
ARTEFACT_NAME="brontoForwarder.zip"

ARTEFACT_PATH="${ROOT_DIR}/${ARTEFACT_NAME}"

cd "${ROOT_DIR}" || exit
zip brontoForwarder function_app.py host.json
cd -

echo "Created artefact: ${ARTEFACT_PATH}"
