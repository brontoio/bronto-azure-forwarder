#!/bin/bash

VERSION="$1"

ROOT_DIR="$(pwd)"
ARTEFACT_NAME="brontoForwarder.zip"

BUILD_DIR="${ROOT_DIR}/build/${VERSION}"
rm -rf "${BUILD_DIR}"
mkdir -p "${BUILD_DIR}"
ARTEFACT_PATH="${BUILD_DIR}/${ARTEFACT_NAME}"

cd "${ROOT_DIR}" || exit
zip brontoForwarder function_app.py host.json
cp "${ARTEFACT_NAME}" "${ARTEFACT_PATH}"
cd -

echo "Created artefact: ${ARTEFACT_PATH}"
