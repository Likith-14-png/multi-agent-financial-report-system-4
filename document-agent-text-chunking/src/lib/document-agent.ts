const pdf = require('pdf-parse');

export async function extractTextFromBuffer(buffer: Buffer, mimeType: string): Promise<string> {
  if (mimeType === 'application/pdf') {
    try {
      const data = await pdf(buffer);
      return data.text;
    } catch (error) {
      console.error('PDF extraction error:', error);
      return '';
    }
  } else if (mimeType === 'text/plain') {
    return buffer.toString('utf-8');
  }
  return '';
}

export function splitTextIntoChunks(text: string, chunkSize: number = 1000, chunkOverlap: number = 200): string[] {
  if (!text) return [];
  
  const chunks: string[] = [];
  let start = 0;
  
  while (start < text.length) {
    let end = start + chunkSize;
    
    // Adjust end to not cut in the middle of a word if possible
    if (end < text.length) {
      const lastSpace = text.lastIndexOf(' ', end);
      if (lastSpace > start) {
        end = lastSpace;
      }
    }
    
    chunks.push(text.slice(start, end).trim());
    
    if (end >= text.length) break;
    
    start = end - chunkOverlap;
    // Ensure we are making progress
    if (start <= 0 && end > 0) start = end - Math.floor(chunkOverlap / 2);
    if (start >= end) start = end - 1; 
  }
  
  return chunks.filter(c => c.length > 0);
}
