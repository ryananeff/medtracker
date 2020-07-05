#! /usr/bin/env bash

set -xe

# `pytest` itself does not set Python path - so it doesn't find the `medtracker`
# module unless you do this.
PYTHONPATH=. pytest
