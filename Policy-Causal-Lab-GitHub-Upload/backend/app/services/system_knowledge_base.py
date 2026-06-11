import hashlib
import json
import re
from sqlalchemy.orm import Session
from ..models import SystemKnowledgeChunk


def chunk_text(text: str, chunk_size=800, overlap=120) -> list[str]:
    if not text:
        return []
    chunks, start = [], 0
    while start < len(text):
        chunks.append(text[start:start + chunk_size])
        start += max(1, chunk_size - overlap)
    return chunks


def save_chunks(db: Session, source_id: int, file_path: str, text: str) -> int:
    chunks = chunk_text(text)
    for index, content in enumerate(chunks):
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        db.add(SystemKnowledgeChunk(source_id=source_id, file_path=file_path, file_type=file_path.rsplit(".", 1)[-1], chunk_index=index, content=content, content_hash=digest, metadata_json=json.dumps({"layer": "system_methodology"}, ensure_ascii=False)))
    db.commit()
    return len(chunks)


def search_chunks(db: Session, query: str, top_k=5, include_content=False) -> list[dict]:
    terms = set(re.findall(r"[\w\u4e00-\u9fff]+", query.lower()))
    rows = db.query(SystemKnowledgeChunk).all()
    scored = []
    for row in rows:
        score = sum(row.content.lower().count(term) for term in terms)
        if score:
            scored.append((score, row))
    result = []
    for score, row in sorted(scored, key=lambda item: item[0], reverse=True)[:top_k]:
        item = {"id": row.id, "source_id": row.source_id, "file_path": row.file_path, "chunk_index": row.chunk_index, "score": score}
        if include_content:
            item["content"] = row.content
        result.append(item)
    return result


def build_hidden_context_for_llm(db: Session, user_query: str, top_k=5) -> tuple[str, list[dict]]:
    refs = search_chunks(db, user_query, top_k, include_content=True)
    context = "\n\n".join(f"[系统方法论知识: {ref['file_path']}#{ref['chunk_index']}]\n{ref['content']}" for ref in refs)
    metadata = [{key: ref[key] for key in ["source_id", "file_path", "chunk_index"]} for ref in refs]
    return context, metadata
