export function normalizeWhitespace(value) {
  /** Collapse whitespace runs to one space and trim both ends. */
  return value.trim().replace(/\s+/g, " ");
}

export function chunkText(value, size) {
  /** Split text into consecutive chunks; size must be a positive integer. */
  if (!Number.isInteger(size) || size <= 0) {
    throw new RangeError("size must be a positive integer");
  }
  const chunks = [];
  for (let index = 0; index < value.length; index += size) {
    chunks.push(value.slice(index, index + size));
  }
  return chunks;
}
