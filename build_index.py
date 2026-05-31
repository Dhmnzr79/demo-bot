import argparse
import glob
import json
import os
import re

import frontmatter
import numpy as np
from dotenv import load_dotenv
from openai import OpenAI

from core.client_runtime import client_md_dir, list_buildable_client_ids, per_client_data_dir

# --- logging (устойчиво) ---
try:
    from logging_setup import log_json, setup_logging
except Exception:
    import logging
    import json as _json

    def log_json(logger, msg, **fields):
        try:
            logger.info(f"{msg} " + _json.dumps(fields, ensure_ascii=False))
        except Exception:
            logger.info(msg)

    def setup_logging():
        logger = logging.getLogger("builder")
        if not logger.handlers:
            h = logging.StreamHandler()
            h.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
            logger.addHandler(h)
            logger.setLevel(logging.INFO)
        return logger


logger = setup_logging()

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("OPENAI_API_KEY is not set in .env")

client = OpenAI(api_key=api_key)
EMB_MODEL = os.getenv("MODEL_EMBED", "text-embedding-3-small")

ALIAS_RX = re.compile(r"<!--\s*aliases:\s*\[(.*?)\]\s*-->", re.I | re.S)


def _norm_alias_key(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"\{#.*?\}", " ", s)
    s = re.sub(r"[^\w\s\-]", " ", s, flags=re.U)
    return re.sub(r"\s+", " ", s).strip()


def _heading_plain_build(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"^#{1,6}\s*", "", s)
    return s


def _chunk_alias_terms_build(row: dict) -> list[str]:
    terms: list[str] = []
    aliases = row.get("aliases") or []
    if isinstance(aliases, list):
        for a in aliases:
            if isinstance(a, str) and a.strip():
                terms.append(a.strip())
    h2 = _heading_plain_build(str(row.get("h2") or ""))
    h3 = _heading_plain_build(str(row.get("h3") or ""))
    h2_id = str(row.get("h2_id") or "").strip()
    h3_id = str(row.get("h3_id") or "").strip()
    if h2:
        terms.append(h2)
    if h3:
        terms.append(h3)
    if h2_id:
        terms.append(h2_id.replace("-", " "))
    if h3_id:
        terms.append(h3_id.replace("-", " "))
    return terms


def extract_local_aliases(block_text: str) -> list[str]:
    m = ALIAS_RX.search(block_text or "")
    if not m:
        return []
    return re.findall(r'"([^"]+)"', m.group(1))


def split_md_to_chunks(text):
    lines = text.splitlines()
    chunks, h2, h2_id, h3, h3_id, buf = [], None, None, None, None, []

    def flush():
        if buf:
            chunks.append(
                {
                    "h2": h2,
                    "h2_id": h2_id,
                    "h3": h3,
                    "h3_id": h3_id,
                    "text": "\n".join(buf).strip(),
                }
            )

    h2rx = re.compile(r"^##\s+(.+?)(?:\s*\{#([a-z0-9\-\_]+)\})?\s*$", re.I)
    h3rx = re.compile(r"^###\s+(.+?)(?:\s*\{#([a-z0-9\-\_]+)\})?\s*$", re.I)
    for ln in lines:
        m2 = h2rx.match(ln)
        m3 = h3rx.match(ln)
        if m2:
            flush()
            buf = []
            h2, h2_id = m2.group(1).strip(), (m2.group(2) or "").strip()
            h3, h3_id = None, None
        elif m3:
            flush()
            buf = []
            h3, h3_id = m3.group(1).strip(), (m3.group(2) or "").strip()
        else:
            buf.append(ln)
    flush()
    return [c for c in chunks if c["text"]]


def embed_batch(texts):
    resp = client.embeddings.create(model=EMB_MODEL, input=texts)
    return [np.array(d.embedding, dtype=np.float32) for d in resp.data]


def text_for_embedding(row):
    parts = []
    if row.get("h2"):
        parts.append(row["h2"])
    if row.get("h3"):
        parts.append(row["h3"])
    if row.get("aliases"):
        parts.append(" | ".join(row["aliases"]))
    clean = ALIAS_RX.sub("", row["text"]).strip()
    parts.append(clean)
    return "\n".join([p for p in parts if p])


def build_client_index(client_id: str) -> None:
    md_root = client_md_dir(client_id)
    out_dir = per_client_data_dir(client_id)
    os.makedirs(out_dir, exist_ok=True)
    corpus: list[dict] = []
    embeds: list[np.ndarray] = []

    pattern = os.path.join(md_root, "**", "*.md")
    paths = sorted(glob.glob(pattern, recursive=True))
    if not paths:
        log_json(logger, "index_build_skip_empty", client_id=client_id, md_root=md_root)
        return

    for path in paths:
        with open(path, "r", encoding="utf-8-sig") as fh:
            fm = frontmatter.load(fh)
        meta = fm.metadata or {}
        doc_id = meta.get("doc_id") or os.path.splitext(os.path.basename(path))[0]
        doc_aliases = meta.get("aliases") or []
        for ch in split_md_to_chunks(fm.content):
            local_aliases = extract_local_aliases(ch["text"])
            item = {
                "doc": doc_id,
                "file": os.path.basename(path),
                "client_id": client_id,
                "topic": meta.get("topic"),
                "doc_type": meta.get("doc_type"),
                "subtype": meta.get("subtype"),
                "cta_action": meta.get("cta_action"),
                "cta_text": meta.get("cta_text"),
                "empathy_enabled": bool(meta.get("empathy_enabled", False)),
                "empathy_tag": meta.get("empathy_tag"),
                "followups": meta.get("followups", []),
                "h2": ch["h2"],
                "h2_id": ch["h2_id"],
                "h3": ch["h3"],
                "h3_id": ch["h3_id"],
                "text": ch["text"],
                "aliases": list(set(doc_aliases + local_aliases)),
            }
            corpus.append(item)

    batch = 64
    for i in range(0, len(corpus), batch):
        texts = [text_for_embedding(c)[:4000] for c in corpus[i : i + batch]]
        embeds.extend(embed_batch(texts))

    arr = np.vstack(embeds).astype(np.float32)
    norms = np.linalg.norm(arr, axis=1, keepdims=True) + 1e-9
    arr = arr / norms

    np.save(os.path.join(out_dir, "embeddings.npy"), arr)
    with open(os.path.join(out_dir, "corpus.jsonl"), "w", encoding="utf-8") as f:
        for row in corpus:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    alias_rows_out: list[dict] = []
    alias_texts: list[str] = []
    for i, row in enumerate(corpus):
        seen_norm: set[str] = set()
        for raw in _chunk_alias_terms_build(row):
            t = (raw or "").strip()
            if not t:
                continue
            nk = _norm_alias_key(t)
            if len(nk) < 2 or nk in seen_norm:
                continue
            seen_norm.add(nk)
            alias_rows_out.append(
                {
                    "corpus_idx": int(i),
                    "client_id": client_id,
                    "file": row.get("file"),
                    "h2_id": row.get("h2_id") or None,
                    "h3_id": row.get("h3_id") or None,
                    "doc_type": row.get("doc_type"),
                    "subtype": row.get("subtype"),
                    "alias_norm": nk,
                    "alias_text": t[:4000],
                }
            )
            alias_texts.append(t[:4000])

    if alias_texts:
        alias_emb_list: list[np.ndarray] = []
        for j in range(0, len(alias_texts), batch):
            alias_emb_list.extend(embed_batch(alias_texts[j : j + batch]))
        a_arr = np.vstack(alias_emb_list).astype(np.float32)
        a_norms = np.linalg.norm(a_arr, axis=1, keepdims=True) + 1e-9
        a_arr = a_arr / a_norms
    else:
        a_arr = np.zeros((0, int(arr.shape[1])), dtype=np.float32)

    np.save(os.path.join(out_dir, "alias_embeddings.npy"), a_arr)
    with open(os.path.join(out_dir, "alias_rows.jsonl"), "w", encoding="utf-8") as af:
        for meta_row in alias_rows_out:
            af.write(json.dumps(meta_row, ensure_ascii=False) + "\n")

    log_json(
        logger,
        "Index build completed",
        client_id=client_id,
        chunks_count=len(corpus),
        embeddings_shape=arr.shape,
        alias_rows=len(alias_rows_out),
        alias_embeddings_shape=a_arr.shape,
        out_dir=out_dir,
    )
    print(
        f"OK [{client_id}]: chunks={len(corpus)} -> {out_dir}/ "
        f"(alias_rows={len(alias_rows_out)})"
    )


def main():
    parser = argparse.ArgumentParser(description="Build per-client retrieval index")
    parser.add_argument(
        "--client",
        default="all",
        help="Client pack id (demo, cesi, nikadent) or 'all'",
    )
    args = parser.parse_args()
    if args.client == "all":
        targets = list_buildable_client_ids()
    else:
        targets = [args.client.strip()]
    log_json(logger, "Starting index build", clients=targets)
    for cid in targets:
        build_client_index(cid)


if __name__ == "__main__":
    main()
