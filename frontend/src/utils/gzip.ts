/** Gzip-compress bytes for faster upload (IFC may only shrink modestly). */
export async function gzipCompress(input: ArrayBuffer): Promise<Uint8Array> {
  if (typeof CompressionStream === "undefined") {
    return new Uint8Array(input);
  }
  const stream = new Blob([input]).stream().pipeThrough(new CompressionStream("gzip"));
  const buf = await new Response(stream).arrayBuffer();
  return new Uint8Array(buf);
}
