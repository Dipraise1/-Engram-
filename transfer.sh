#!/bin/bash
cd /Users/divine/Documents/engram && source .venv/bin/activate
btcli wallet transfer --wallet.name engram --destination 5CMUm6RVyL9oHBnsvztA36eg59DunTutvuYDhHcWXhVd1J8K --amount 10 --subtensor.network test --no-prompt
