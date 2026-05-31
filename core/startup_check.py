"""Validate per-client index artifacts before app serves traffic."""
from __future__ import annotations

import json
import logging
import os
import sys

import numpy as np

from core.client_runtime import client_pack_dir, corpus_paths, list_buildable_client_ids
from logging_setup import log_json


def run_startup_check(logger: logging.Logger) -> None:
    client_ids = list_buildable_client_ids()
    if not client_ids:
        logger.error("startup_check_failed: no client packs with md/")
        sys.exit(1)

    total_chunks = 0
    for cid in client_ids:
        paths = corpus_paths(cid)
        emb_path = paths["embeddings"]
        corpus_path = paths["corpus"]
        catalog_path = os.path.join(client_pack_dir(cid), "service_catalog.json")
        prices_path = os.path.join(client_pack_dir(cid), "prices.json")

        if not os.path.isfile(emb_path):
            logger.error("startup_check_failed: embeddings missing for %s: %s", cid, emb_path)
            sys.exit(1)
        try:
            arr = np.load(emb_path)
            if not isinstance(arr, np.ndarray):
                logger.error("startup_check_failed: embeddings not ndarray for %s", cid)
                sys.exit(1)
        except Exception as e:
            logger.error("startup_check_failed: cannot read embeddings %s: %s", emb_path, e)
            sys.exit(1)

        if not os.path.isfile(corpus_path):
            logger.error("startup_check_failed: corpus missing for %s: %s", cid, corpus_path)
            sys.exit(1)
        try:
            with open(corpus_path, "r", encoding="utf-8") as f:
                chunks = sum(1 for line in f if line.strip())
        except Exception as e:
            logger.error("startup_check_failed: cannot read corpus %s: %s", corpus_path, e)
            sys.exit(1)
        if chunks == 0:
            logger.error("startup_check_failed: empty corpus for %s: %s", cid, corpus_path)
            sys.exit(1)
        total_chunks += chunks

        for label, path in (("service_catalog", catalog_path), ("prices", prices_path)):
            if not os.path.isfile(path):
                logger.error("startup_check_failed: %s missing for %s: %s", label, cid, path)
                sys.exit(1)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    obj = json.load(f)
                if not isinstance(obj, dict):
                    logger.error("startup_check_failed: %s must be object for %s", label, cid)
                    sys.exit(1)
            except Exception as e:
                logger.error("startup_check_failed: invalid %s for %s: %s", label, cid, e)
                sys.exit(1)

    log_json(logger, "startup_check_ok", clients=client_ids, chunks=total_chunks)
