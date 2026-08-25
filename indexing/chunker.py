# ============================================================
# indexing/chunker.py — Token-Based Text Chunker
# ============================================================
# Tokenizer is passed in explicitly instead of being a module-level
# global (core.clients.AppClients.tokenizer, loaded once at
# app/script startup).
# ============================================================


def split_text_into_token_chunks(
    text         : str,
    parent_id    : str,
    tokenizer,
    chunk_size   : int,
    overlap_size : int,
) -> list[dict]:
    """
    Split a long text into overlapping token-based child chunks.

    Args:
        text        : The full text to split.
        parent_id   : Identifier for the parent document, e.g.
                      "GSE254430_overall_design".
        tokenizer   : HuggingFace tokenizer instance
                      (core.clients.AppClients.tokenizer).
        chunk_size  : Tokens per child chunk (settings.CHUNK_SIZE_TOKENS).
        overlap_size: Overlapping tokens between chunks
                      (settings.CHUNK_OVERLAP_TOKENS).

    Returns:
        List of {"text": str, "parent_id": str, "child_index": int}.
    """

    if not text or not text.strip():
        return []

    token_ids = tokenizer.encode(text, add_special_tokens=False)

    if len(token_ids) <= chunk_size:
        return [{"text": text.strip(), "parent_id": parent_id, "child_index": 0}]

    child_chunks = []
    child_index  = 0
    step_size    = chunk_size - overlap_size

    start_position = 0

    while start_position < len(token_ids):

        end_position    = start_position + chunk_size
        chunk_token_ids = token_ids[start_position:end_position]

        chunk_text = tokenizer.decode(
            chunk_token_ids,
            skip_special_tokens          = True,
            clean_up_tokenization_spaces = True,
        )

        if chunk_text.strip():
            child_chunks.append({
                "text"        : chunk_text.strip(),
                "parent_id"   : parent_id,
                "child_index" : child_index,
            })
            child_index += 1

        start_position += step_size

        remaining_tokens = len(token_ids) - start_position
        if remaining_tokens < int(chunk_size * 0.2):
            break

    return child_chunks
