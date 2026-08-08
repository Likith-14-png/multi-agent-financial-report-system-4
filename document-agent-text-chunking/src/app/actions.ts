'use server';

import { db } from '@/db';
import { documents, chunks } from '@/db/schema';
import { extractTextFromBuffer, splitTextIntoChunks } from '@/lib/document-agent';
import { revalidatePath } from 'next/cache';
import { eq } from 'drizzle-orm';

export async function uploadDocument(formData: FormData) {
  const file = formData.get('file') as File;
  if (!file) return { error: 'No file provided' };

  const buffer = Buffer.from(await file.arrayBuffer());
  
  try {
    // 1. Create document entry
    const [doc] = await db.insert(documents).values({
      name: file.name,
      type: file.type,
      status: 'processing',
    }).returning();

    // 2. Extract text
    const text = await extractTextFromBuffer(buffer, file.type);
    
    if (!text) {
      await db.update(documents)
        .set({ status: 'failed' })
        .where(eq(documents.id, doc.id));
      return { error: 'Failed to extract text' };
    }

    // 3. Chunk text
    const textChunks = splitTextIntoChunks(text);
    
    // 4. Store chunks
    const chunkValues = textChunks.map((content, index) => ({
      documentId: doc.id,
      content,
      chunkIndex: index,
      metadata: { source: file.name, length: content.length },
    }));

    if (chunkValues.length > 0) {
      await db.insert(chunks).values(chunkValues);
    }

    // 5. Update status
    await db.update(documents)
      .set({ status: 'processed' })
      .where(eq(documents.id, doc.id));

    revalidatePath('/');
    return { success: true, documentId: doc.id };
  } catch (error) {
    console.error('Upload error:', error);
    return { error: 'Internal server error' };
  }
}


